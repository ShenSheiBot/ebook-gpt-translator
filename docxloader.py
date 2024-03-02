from docx import Document
from docx.text.paragraph import Paragraph
from translate import translate, validate, SqlWrapper
from utils import load_config
from loguru import logger
import string
import re
import argparse


# Load the configuration
config = load_config()


def is_title(paragraph):
    # List of words that are not usually capitalized in a title
    exceptions = {
        'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'in',
        'nor', 'of', 'on', 'or', 'the', 'up'
    }

    # Remove punctuation using str.translate and string.punctuation
    translator = str.maketrans('', '', string.punctuation)
    cleaned_paragraph = paragraph.translate(translator)

    # Check if the cleaned paragraph is all uppercase
    # Numbers and symbols will be ignored by isupper()
    if cleaned_paragraph.replace(" ", "").isupper():
        return True

    # Split the cleaned paragraph into words
    words = cleaned_paragraph.split()

    # Check if the cleaned paragraph is likely a title based on the capitalization
    for i, word in enumerate(words):
        # Remove any remaining non-alphanumeric characters
        word = re.sub(r'[^A-Za-z0-9]+', '', word)
        # The first and last word should be capitalized
        if i == 0 or i == len(words) - 1:
            if not word.istitle() and not word.isupper():
                return False
        # Words that are not exceptions should be capitalized
        elif word.lower() not in exceptions:
            if not word.istitle() and not word.isupper():
                return False
        # Exception words in the middle of a title should not be capitalized
        else:
            if word.isupper() or (word.istitle() and word.lower() in exceptions):
                return False

    # The string passes the title checks
    return True


def is_bold(paragraph):
    for run in paragraph.runs:
        if not run.bold:
            return False
    return True


def get_style(paragraph):
    # Find the run with the highest number of characters
    longest_run = None
    max_length = 0
    for run in paragraph.runs:
        if len(run.text) > max_length:
            longest_run = run
            max_length = len(run.text)
    if longest_run:
        return longest_run.style, longest_run.font.size
    else:
        return None


def add_text_to_paragraph(paragraph, new_text):
    """
    Add text to a given Paragraph object, using the style and font size of the run with the highest character count.

    Parameters:
    - paragraph: A docx.text.paragraph.Paragraph object.
    - new_text: The text to add to the paragraph.
    """
    # If new_text is all digit, do nothing
    if new_text.isdigit():
        return
    
    # Check if the input is a Paragraph object
    if not isinstance(paragraph, Paragraph):
        raise TypeError("The provided paragraph must be a docx.text.paragraph.Paragraph object.")

    result = get_style(paragraph)

    # Add new text at the end of the paragraph with the same style and font size
    if result:
        style, font_size = result
        new_run = paragraph.add_run(new_text)
        new_run.style = style
        if font_size:
            new_run.font.size = font_size
        # Check if the entire paragraph is bold
        if is_bold(paragraph):
            new_run.bold = True
    else:
        # Paragraph has no runs, so we add the text as a new run
        # This will inherit the paragraph's style by default
        paragraph.add_run(new_text)
        
        
def is_page_number(paragraph):
    # If a paragraph begins/ends by numbers and < 10 words, without period, it's likely a page number
    first_word = paragraph.text.strip().split()[0]
    last_word = paragraph.text.strip().split()[-1]
    if (first_word.isdigit() or last_word.isdigit()) \
    and len(paragraph.text.split()) < 10 and "." not in paragraph.text:
        return True
    return False


def translate_doc(docx_filename, output_filename, args):
    # Load the document
    doc = Document(docx_filename)
    
    # Remove pargraphs with empty content
    last_char = ''
    style = None
    prev_paragraph = None
    paragraph_maps = {}
    final_paragraphs = set()
    
    # Iterate over each paragraph in the document
    for i, paragraph in enumerate(doc.paragraphs):
        # logger.debug(paragraph.text.strip())
        if paragraph.text.strip() == "":
            continue
        elif is_title(paragraph.text.strip()) or is_page_number(paragraph) or is_bold(paragraph):
            # logger.error(f"Title or page number")
            final_paragraphs.add(i)
            continue
        elif ((last_char.isalnum() or last_char == ',') and
              (paragraph.text.strip()[0].isalnum() and paragraph.text.strip()[0].islower())) \
        and get_style(paragraph) == style:
            # Continuation of previous paragraph
            # logger.error(f"Continuation")
            last_char = paragraph.text.strip()[-1]
            paragraph_maps[i] = prev_paragraph
            prev_paragraph = i
        else:
            # New paragraph
            # logger.error(f"New paragraph")
            last_char = paragraph.text.strip()[-1]
            style = get_style(paragraph)
            if prev_paragraph:
                final_paragraphs.add(prev_paragraph)
            prev_paragraph = i
            paragraph_maps[i] = None
    if prev_paragraph:
        final_paragraphs.add(prev_paragraph)
            
    with SqlWrapper(f'output/{config["CN_TITLE"]}/buffer.db') as cache:
        for i, p in enumerate(doc.paragraphs):
            if i not in final_paragraphs:
                continue
            text_to_translate = p.text.strip()
            while i in paragraph_maps and paragraph_maps[i]:
                text_to_translate = doc.paragraphs[paragraph_maps[i]].text.strip() + " " + text_to_translate
                i = paragraph_maps[i]
            if text_to_translate in cache and validate(text_to_translate, cache[text_to_translate]):
                translated_text = cache[text_to_translate]
            elif text_to_translate.isdigit():
                continue
            else:
                translated_text = translate(text_to_translate, args.dryrun)
                if not args.dryrun:
                    cache[text_to_translate] = translated_text
            add_text_to_paragraph(p, "\n" + translated_text)
    doc.save(output_filename)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dryrun", action="store_true")
    args = parser.parse_args()
    
    if args.dryrun:
        logger.warning("Dry run mode enabled. No translation will be performed.")
    
    logger.add(f"output/{config['CN_TITLE']}/info.log", colorize=True, level="DEBUG")
    # Replace 'input.docx' with the path to your document and specify the output filename
    translate_doc(f'output/{config["CN_TITLE"]}/input.docx', f'output/{config["CN_TITLE"]}/output.docx', args)
