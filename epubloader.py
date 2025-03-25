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
from translate import translate, align_translate, validate, SqlWrapper
from utils import load_config, update_content, get_filtered_tags, replace_section_titles, postprocess
from utils import wrap_text, unwrap_text


warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)
warnings.filterwarnings('ignore', category=UserWarning)
with open("translation.yaml", "r") as f:
    translation_config = yaml.load(f, Loader=yaml.FullLoader)
webapp = None
MAX_LENGTH = 4000


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
    if book.uid is None:
        import uuid
        book.set_identifier(str(uuid.uuid4()))
    
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
        ncx = None
        for item in book.get_items():
            if isinstance(item, epub.EpubNcx):
                ncx = item
                break
        
        if ncx:
            content = ncx.content.decode("utf-8")
            soup = BeautifulSoup(content, "html5lib")
            navpoints = soup.find_all("navpoint")
            jp_titles = []
            for navpoint in navpoints:
                name = navpoint.find('text').get_text(strip=True)
                jp_titles.append(name)
            
            # Traverse the aggregated chapter titles
            align_translate(jp_titles, title_buffer, args.dryrun)
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
                content = wrap_text(item.content.decode("utf-8"))
                soup = BeautifulSoup(content, "html5lib")
                cn_soup = BeautifulSoup(content, "html5lib")
                
                for rt_tag in soup.find_all("rt"):
                    rt_tag.decompose()
                for rt_tag in cn_soup.find_all("rt"):
                    rt_tag.decompose()
                
                titles_and_paragraphs = get_filtered_tags(soup)
                cn_titles_and_paragraphs = get_filtered_tags(cn_soup)
                
                last_text = None
                for title, cnonly in zip(titles_and_paragraphs, cn_titles_and_paragraphs):
                    if title.name in ['h1', 'h2', 'h3']:
                        jp_title = title.get_text().strip()
                        if jp_title in title_buffer and validate(jp_title, title_buffer[jp_title]):
                            cn_title = title_buffer[jp_title]
                        else:
                            ### Start translation
                            if args.polish:
                                cn_title = jp_title
                            elif re.sub(r'\s', '', jp_title) == re.sub(r'\s', '', config['JP_TITLE']):
                                cn_title = config['CN_TITLE']
                            else:
                                cn_title = translate(jp_title, dryrun=args.dryrun)
                                if not args.dryrun:
                                    title_buffer[jp_title] = cn_title
                            ### Translation finished
                        cn_title = postprocess(cn_title)
                            
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
                        
                        def translate_helper(jp_text):
                            ### Start translation
                            if jp_text in buffer and validate(jp_text, buffer[jp_text]):
                                cn_text = buffer[jp_text]
                            else:
                                cn_text = translate(jp_text, dryrun=args.dryrun)
                                if not args.dryrun:
                                    buffer[jp_text] = cn_text
                            ### Translation finished
                            cn_text = postprocess(cn_text)
                            return cn_text
                        
                        if len(jp_text) > MAX_LENGTH:
                            # Split the title into smaller chunks by paragraphs
                            jp_text_chunks = jp_text.split("\n\n")
                            cn_text_chunks = []
                            for i in range(len(jp_text_chunks)):
                                if len(jp_text_chunks[i].strip()) > 0:
                                    cn_text_chunks.append(translate_helper(jp_text_chunks[i]))
                            cn_text = "\n\n".join(cn_text_chunks)
                        else:
                            cn_text = translate_helper(jp_text)
                        
                        new_text = soup.new_tag(title.name, **{k: v for k, v in title.attrs.items()})
                        new_text.string = cn_text
                        if cnonly.parent:
                            cnonly.insert_after(deepcopy(new_text))
                        else:
                            last_text.insert_after(deepcopy(new_text))
                        cnonly.decompose()
                        title.insert_after(new_text)
                        last_text = new_text

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
