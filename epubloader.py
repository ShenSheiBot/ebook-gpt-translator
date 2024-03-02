from ebooklib import epub
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from copy import deepcopy
import argparse
import re
from tqdm import tqdm
from loguru import logger
import re
import warnings
import yaml
import time
from translate import translate, validate, SqlWrapper
from utils import load_config, update_content, remove_leading_numbers, get_leading_numbers
from utils import split_string_by_length, txt_to_html, replace_section_titles


warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)
warnings.filterwarnings('ignore', category=UserWarning)
with open("translation.yaml", "r") as f:
    translation_config = yaml.load(f, Loader=yaml.FullLoader)
webapp = None


def main():
    config = load_config()
    logger.add(f"output/{config['CN_TITLE']}/info.log", colorize=True, level="DEBUG")
    parser = argparse.ArgumentParser()
    parser.add_argument("--dryrun", action="store_true")
    parser.add_argument("--polish", action="store_true")
    args = parser.parse_args()
    
    if args.dryrun:
        logger.warning("Dry run mode enabled. No translation will be performed.")

    # Open the EPUB file
    book = epub.read_epub(f"output/{config['CN_TITLE']}/input.epub", {"ignore_ncx": False})
    modified_book = deepcopy(book)
    modified_book.items = []
    cn_book = deepcopy(book)
    cn_book.items = []

    with SqlWrapper(f"output/{config['CN_TITLE']}/buffer.db") as buffer, \
         SqlWrapper(f"output/{config['CN_TITLE']}/title_buffer.db") as title_buffer:
             
        # Iterate through each item in the book (chapters, sections, etc.)
        if config['JP_TITLE'] not in title_buffer:
            title_buffer[config['JP_TITLE']] = config['CN_TITLE']
        
        ############ Translate the chapter titles ############
        ncx = book.get_item_with_id("ncx")
        content = ncx.content.decode("utf-8")
        soup = BeautifulSoup(content, "html5lib")
        navpoints = soup.find_all("navpoint")
        output = ""
        jp_titles = []
        for i, navpoint in enumerate(navpoints):
            name = navpoint.find('text').get_text(strip=True)
            output += str(i) + " " + name + "\n"
            jp_titles.append(name)
        jp_titles_parts = split_string_by_length(output, 800)
        
        # Traverse the aggregated chapter titles
        for jp_text in jp_titles_parts:
            jp_titles_ = jp_text.strip().split('\n')
            new_jp_titles = []
            # Concatenate title to the previous one if it's a continuation
            for jp_title in jp_titles_:
                if jp_title[0].isdigit():
                    new_jp_titles.append(jp_title)
                else:
                    new_jp_titles[-1] += jp_title
            jp_titles_ = new_jp_titles
            
            start_idx = get_leading_numbers(jp_titles_[0])
            end_idx = get_leading_numbers(jp_titles_[-1])
            
            if not all([remove_leading_numbers(title) in title_buffer for title in jp_titles_]):
                cn_titles_ = []
                title_retry_count = int(config['TRANSLATION_TITLE_RETRY_COUNT']) + 1
                
                while len(cn_titles_) != len(jp_titles_) and title_retry_count > 0:
                    ### Start translation
                    if args.polish:
                        cn_text = jp_text
                    elif jp_text in title_buffer:
                        cn_text = title_buffer[jp_text]
                    else:
                        cn_text = translate(jp_text, mode="title_translation", dryrun=args.dryrun)
                        if not args.dryrun:
                            title_buffer[jp_text] = cn_text
                    ### Translation finished
                    
                    ### Match translated title to the corresponding indices
                    cn_titles_ = cn_text.strip().split('\n')
                    cn_titles_ = [title for title in cn_titles_ if get_leading_numbers(title) is not None]
                    if len(cn_titles_) == 0:
                        continue
                    if get_leading_numbers(cn_titles_[0]) == start_idx and \
                        get_leading_numbers(cn_titles_[-1]) == end_idx and \
                            len(cn_titles_) == len(jp_titles_):
                        break
                    else:
                        title_retry_count -= 1
                
                if len(cn_titles_) != len(jp_titles_):
                    raise ValueError("Title translation failed.")
                    
                for cn_title, jp_title in zip(cn_titles_, jp_titles_):
                    cn_title = jp_title
                    title_buffer[remove_leading_numbers(jp_title)] = remove_leading_numbers(cn_title)

        replace_section_titles(cn_book.toc, title_buffer)
        replace_section_titles(modified_book.toc, title_buffer, cnjp=True)
        
        total_items = 0
        for item in tqdm(list(book.get_items())):
            if isinstance(item, epub.EpubHtml) and not isinstance(item, epub.EpubNav) \
            and "TOC" not in item.id and "toc" not in item.id:
                total_items += 1
        current_items = 0
        current_time = None
    
        ############ Translate the chapters and TOCs ############
        for item in list(book.get_items()):
            
            if isinstance(item, epub.EpubHtml) and not isinstance(item, epub.EpubNav) \
            and "TOC" not in item.id and "toc" not in item.id:
                
                current_items += 1
                logger.info(f"Translating {item.id} ({current_items}/{total_items}) ...")
                # Estimate remaining time
                if current_items > 1:
                    elapsed_time = time.time() - current_time
                    remaining_time = elapsed_time * (total_items - current_items)
                    logger.info(f"Estimated remaining time: {remaining_time / 60:.2f} minutes")
                current_time = time.time()
                
                # Parse HTML and extract text
                soup = BeautifulSoup(item.content.decode("utf-8"), "html5lib")
                cn_soup = BeautifulSoup(item.content.decode("utf-8"), "html5lib")
                
                for rt_tag in soup.find_all("rt"):
                    rt_tag.decompose()
                for rt_tag in cn_soup.find_all("rt"):
                    rt_tag.decompose()
                
                titles_and_paragraphs = soup.find_all(['h1', 'h2', 'h3', 'p'])
                cn_titles_and_paragraphs = cn_soup.find_all(['h1', 'h2', 'h3', 'p'])
                
                for title, cnonly in zip(titles_and_paragraphs, cn_titles_and_paragraphs):
                    if title.name in ['h1', 'h2', 'h3']:
                        jp_title = title.get_text().strip()
                        if jp_title in title_buffer:
                            cn_title = title_buffer[jp_title]
                        else:
                            ### Start translation
                            if args.polish:
                                cn_title = jp_title
                            elif re.sub(r'\s', '', jp_title) == re.sub(r'\s', '', config['JP_TITLE']):
                                cn_title = config['CN_TITLE']
                            else:
                                cn_title = translate(jp_title, dryrun=args.dryrun)
                                title_buffer[jp_title] = cn_title
                            ### Translation finished
                            
                        new_title = soup.new_tag(title.name, **{k: v for k, v in title.attrs.items()})
                        new_title.string = title.get_text().replace(jp_title, cn_title)
                        cnonly.insert_after(deepcopy(new_title))
                        cnonly.decompose()
                        title.insert_after(new_title)
                    else:
                        jp_text = title.get_text().strip()
                        if len(jp_text.strip()) == 0:
                            continue
                        # Remove images
                        img_pattern = re.compile(r'<img[^>]+>')
                        imgs = img_pattern.findall(jp_text)
                        jp_text = img_pattern.sub('', jp_text)
                        
                        if jp_text in buffer and validate(jp_text, buffer[jp_text]):
                            cn_text = buffer[jp_text]
                        else:
                            cn_text = translate(jp_text, dryrun=args.dryrun)
                            if not args.dryrun:
                                buffer[jp_text] = cn_text
                        cn_text = txt_to_html(cn_text)
                        new_text = BeautifulSoup(cn_text, "html5lib").find()
                        cnonly.insert_after(deepcopy(new_text))
                        cnonly.decompose()
                        title.insert_after(new_text)

                        for img in imgs:
                            cnonly.insert_before(BeautifulSoup(img, "html5lib"))
                            title.insert_before(BeautifulSoup(img, "html5lib"))
                    
                update_content(item, modified_book, title_buffer, soup)
                update_content(item, cn_book, title_buffer, cn_soup)
                
            ### Handle TOC and Ncx updates
            elif isinstance(item, epub.EpubNcx) or \
            (isinstance(item, epub.EpubHtml) and ("TOC" in item.id or "toc" in item.id)):
                    
                # Update titles to CN titles or CN+JP titles in TOC
                content = item.content.decode("utf-8")
                cn_content = deepcopy(content)
                for jp_title in jp_titles:
                    if jp_title in title_buffer:
                        cn_title = title_buffer[jp_title]
                        content = content.replace(jp_title, cn_title)
                        cn_content = cn_content.replace(jp_title, cn_title)
                
                update_content(item, modified_book, title_buffer, content)
                update_content(item, cn_book, title_buffer, cn_content)
            
            else:
                # Copy other items
                modified_book.items.append(item)
                cn_book.items.append(item)
    
    # Save EPUB output
    namespace = 'http://purl.org/dc/elements/1.1/'
    
    cn_book.metadata[namespace]['language'] = []
    cn_book.set_language("zh")
    cn_book.metadata[namespace]['title'] = []
    cn_book.set_title(config['CN_TITLE'])
    modified_book.metadata[namespace]['language'] = []
    modified_book.set_language("zh")
    modified_book.metadata[namespace]['title'] = []
    modified_book.set_title(config['CN_TITLE'])
    
    epub.write_epub(f"output/{config['CN_TITLE']}/{config['CN_TITLE']}_cnen.epub", modified_book)
    epub.write_epub(f"output/{config['CN_TITLE']}/{config['CN_TITLE']}_cn.epub", cn_book)


if __name__ == "__main__":
    main()
