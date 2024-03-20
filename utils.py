import random
import re
import os
import ast
from loguru import logger
from copy import deepcopy
from ebooklib import epub
import json
from bs4 import BeautifulSoup, Tag


def load_config(filepath=".env"):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(script_dir, filepath)
    config = {}
    with open(filepath, "r", encoding="utf-8") as file:
        for line in file:
            if line.startswith("#"):
                continue
            if line.strip():
                key, value = line.strip().split("=", 1)
                key = key.strip()
                value = value.strip()
                # Remove quotes if value is a string that's quoted
                if len(value) < 1:
                    continue
                if (value[0] == value[-1]) and value.startswith(("'", '"')):
                    value = value[1:-1]
                # Try to evaluate value as int or float
                try:
                    value = ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    pass
                config[key] = value
    return config


def remove_leading_numbers(text):
    return re.sub(r"^\d+\.?", "", text).strip()


def get_leading_numbers(text):
    result = re.match(r"\d+", text)
    if result is None:
        return None
    return int(result.group(0))


def txt_to_html(text, tag="p"):
    paragraphs = text.strip().split("\n")
    html_paragraphs = [
        f"<{tag}>" + p.strip() + f"</{tag}>" for p in paragraphs if p.strip() != ""
    ]
    return "\n".join(html_paragraphs)


def get_filtered_tags(soup):
    def is_eligible_div(tag):
        # A div is eligible if it does not contain any of the specified tags
        return tag.name == 'div' and not tag.find_all(['h1', 'h2', 'h3', 'p', 'div'])

    # Find all eligible elements, including divs
    eligible_elements = soup.find_all(['h1', 'h2', 'h3', 'p']) + soup.find_all(is_eligible_div)
    
    # Sort elements by their position in the document
    sorted_elements = sorted(eligible_elements, key=lambda x: x.parent.contents.index(x))

    return sorted_elements


def split_string_by_paragraphs(text):
    return [p for p in text.split("\n") if p.strip() != ""]


def split_string_by_length(text, max_length=1000):
    parts = []
    while len(text) > max_length:
        split_index = text.rfind("\n", 0, max_length)
        while split_index == 0:
            text = text[1:]
            split_index = text.rfind("\n", 0, max_length)
        if split_index == -1:
            split_index = max_length
        parts.append(text[:split_index].strip())
        text = text[split_index:]
    if len(text) > 0:
        parts.append(text.strip())

    return parts


def sep():
    return BeautifulSoup("<hr>", "html.parser")


def load_prompt(filename="resource/promptv2.txt"):
    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()
        return content


def load_random_paragraph(filename="resource/sample.txt", num_chars=500):
    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()
        content_length = len(content)

        if content_length < num_chars:
            raise ValueError(f"File {filename} does not contain enough characters.")

        start_index = random.randint(0, content_length - num_chars)
        return content[start_index:start_index + num_chars]


def replace_quotes(text):
    text = text.replace("“", "「")
    text = text.replace("”", "」")
    text = text.replace("〔", "「")
    text = text.replace("〕", "」")
    text = text.replace("‘", "『")
    text = text.replace("’", "』")
    text = re.sub(r'"(.*?)"', r"「\1」", text)
    text = re.sub(r"'(.*?)'", r"『\1』", text)
    return text


def fix_repeated_chars(line):
    pattern = r"([！a-zA-Z0-9_\u4E00-\u9FFF\u3040-\u30FF])\1{5,}"
    line = re.sub(pattern, r"\1\1\1\1\1", line)
    line = re.sub(r"[\.]{6,}", "……", line)
    line = re.sub(r"[\.]{4,5}", "…", line)
    line = replace_quotes(line)
    return line


def has_repeated_chars(line):
    pattern = r"([a-zA-Z0-9_\u4E00-\u9FFF\u3040-\u30FF])\1{5,}"
    return bool(re.search(pattern, line))


def check_jp(text, percentage=0.3):
    """Return True if over 30% of the chars in the text are hiragana and katakana, False otherwise."""
    total_chars = len(text)
    hiragana_katakana_chars = sum(1 for char in text if is_jp(char))
    if total_chars == 0:
        return False
    return (hiragana_katakana_chars / total_chars) > percentage


def is_jp(char):
    """Return True if the character is hiragana or katakana, False otherwise."""
    return "\u3040" <= char <= "\u309F" or "\u30A0" <= char <= "\u30FF"


def remove_punctuation(text):
    # Define a pattern to match Latin, Chinese, and Japanese punctuation
    pattern = (
        r"[!\"#$%&\'()*+,-./:;<=>?@\[\\\]^_`{|}~\u3000-\u303F\uFF00-\uFFEF「」『』…]"
    )
    # Use re.sub() to replace the matched punctuation with an empty string
    return re.sub(pattern, "", text)


def find_first_east_asian(input_string):
    # Use regex to find the first East Asian character
    match = re.search("[\u2E80-\u9FFF\uF900-\uFAFF\uFE30-\uFE4F]", input_string)

    # If an East Asian character is found, return the string from that character onwards
    if match:
        return input_string[match.start():]
    else:
        # If no East Asian character is found, return an empty string
        return ""


def replace_ge(text):
    pattern = re.compile(r"(ge|Ge){2,}", re.IGNORECASE)

    def replacement(match):
        ge_count = len(match.group()) // 2
        return "咯" * ge_count

    return pattern.sub(replacement, text)


def replace_ga(text):
    pattern = re.compile(r"(ga|Ga){2,}", re.IGNORECASE)

    def replacement(match):
        ge_count = len(match.group()) // 2
        return "嘎" * ge_count

    return pattern.sub(replacement, text)


def replace_goro(text):
    pattern = re.compile(r"こ(こ|ろ){3,}", re.IGNORECASE)

    def replacement(match):
        matched_string = match.group()
        return matched_string.replace("こ", "咕").replace("ろ", "噜")

    return pattern.sub(replacement, text)


def replace_uoraaa(text):
    pattern = re.compile(r"う[ぉお]ら[ぁあ]+")
    replacement = "欧啦啦啦"
    return pattern.sub(replacement, text)


def replace_repeater_char(text):
    def replacer(match):
        char_before = match.group(1)
        return char_before + char_before

    pattern = r"(.)々"
    return re.sub(pattern, replacer, text)


def has_kana(text):
    return bool(re.search(r"[\u3040-\u309F\u30A0-\u30FA\u30FC-\u30FF]+", text))


def has_chinese(text):
    return bool(re.search(r"[\u4E00-\u9FFF]+", text))


def remove_duplicate(text):
    if "-----以下是" in text:
        lines = text.split("\n")
        filtered_lines = []
        flag = False
        for line in lines:
            if "-----以下是" in line:
                flag = True
                continue
            if flag:
                filtered_lines.append(line)
                logger.info("Kept line after 以下是: " + line)
            else:
                logger.info("Removed line before 以下是: " + line)
        text = "\n".join(filtered_lines)
    return text


def remove_spaces_from_chinese(text):
    # This regex finds any space that is between two Chinese characters (Unicode range for CJK)
    pattern = re.compile(r"(?<=[\u4e00-\u9fff])[ \t]+(?=[\u4e00-\u9fff])")
    return pattern.sub("", text)


def contains_arabic_characters(check_string):
    arabic_pattern = re.compile(
        r"[\u0600-\u06FF]"
    )  # includes the range of Arabic characters
    return bool(arabic_pattern.search(check_string))


def contains_tibetan_characters(check_string):
    tibetan_pattern = re.compile(
        r"[\u0F00-\u0FFF]"
    )  # includes the range of Tibetan characters
    return bool(tibetan_pattern.search(check_string))


def contains_russian_characters(check_string):
    check_string = check_string.replace("Д", "")
    russian_pattern = re.compile(
        r"[А-яёЁ]"
    )  # includes the range of Russian characters and the letter Ё/ё
    return bool(russian_pattern.search(check_string))


def num_failure(input, text, name_convention=None):
    count = 0
    if name_convention is not None:
        for jp_name, cn_name in name_convention.items():
            if jp_name in input and (
                cn_name not in text
                and cn_name.replace("·", "・") not in text
                and cn_name.replace("・", "·") not in text
                and jp_name not in text
                and jp_name.replace(" ", "") not in text
            ):
                count += 1
    return count


## Remove header
def remove_header(text):
    first_line = text.split("\n")[0]
    if "翻译" in first_line and "：" in first_line:
        text = "\n".join(text.split("\n")[1:])
    return text


def detect_language(text):
    # Counters for Japanese and English characters
    hiragana_count = 0
    katakana_count = 0
    english_count = 0

    # Removing non-word characters
    cleaned_text = "".join(e for e in text if e.isalnum())

    # Total characters (excluding special characters and punctuation)
    total_characters = len(cleaned_text)

    # Check for empty string
    if total_characters == 0:
        return "Indeterminate"

    # Calculate counts of each character type
    for char in cleaned_text:
        # Checking Unicode ranges for Hiragana, Katakana, and English
        if "\u3040" <= char <= "\u309F":
            hiragana_count += 1
        elif "\u30A0" <= char <= "\u30FF":
            katakana_count += 1
        elif ("\u0041" <= char <= "\u005A") or ("\u0061" <= char <= "\u007A"):
            english_count += 1

    # Calculate character type ratios
    japanese_ratio = (hiragana_count + katakana_count) / total_characters
    english_ratio = english_count / total_characters

    # Apply the given conditions
    if japanese_ratio > 0.3:
        return "Japanese"
    elif english_ratio > 0.7:
        return "English"
    else:
        return "Chinese"


def replace_section_titles(nested_list, title_buffer, cnjp=False):
    for element in nested_list:
        if isinstance(element, list) or isinstance(element, tuple):
            replace_section_titles(element, title_buffer, cnjp)
        elif hasattr(element, "title"):
            if element.title in title_buffer:
                if cnjp:
                    element.title = title_buffer[element.title] + " | " + element.title
                else:
                    element.title = title_buffer[element.title]
    return nested_list


def update_content(item, new_book, title_buffer, updated_content):
    if type(updated_content) is str:
        soup = BeautifulSoup(updated_content, "html5lib")
    else:
        assert type(updated_content) is BeautifulSoup
        soup = updated_content

    for a_tag in soup.find_all("a"):
        jp_text = a_tag.get_text()
        if jp_text in title_buffer:
            a_tag.string = title_buffer[jp_text]

    modified_item = deepcopy(item)
    modified_item.set_content(soup.encode("utf-8"))
    new_book.items.append(modified_item)

    if isinstance(item, epub.EpubHtml):
        links = soup.find_all("link")
        for link in links:
            if "href" not in link.attrs:
                continue
            href = link.attrs["href"]
            if href.endswith("css"):
                modified_item.add_link(href=href, rel="stylesheet", type="text/css")


def get_first_p_after_all_headers(headers):
    if not headers:
        return None
    last_header = headers[-1]
    for sibling in last_header.find_all_next(["p"]):
        if sibling.get_text(strip=True):
            return sibling
    return None


def find_matching_p_to_titles(soup, jp_titles, fast=False):
    matching_ps = []  # List to store matching p tags
    matching_titles = []  # List to store corresponding titles

    # Iterate over all p tags in the HTML
    for p_tag in soup.find_all("p"):
        p_text = p_tag.get_text(strip=True)

        # Iterate over all the given titles
        for jp_title in jp_titles:
            jp_title_stripped = jp_title.strip()

            if jp_title_stripped == p_text:
                matching_ps.append(p_tag)
                matching_titles.append(jp_title)
                if fast:
                    return matching_ps, matching_titles
                break  # Assuming only one jp_title will match, we break after finding it

    # Return the pair of lists
    return matching_ps, matching_titles


def get_consecutive_name_entities(entities, score_threshold=0.9):
    # Initialize variables
    consecutive_entities = []
    current_entity = None
    current_entity_score = 0.0
    current_entity_text = ""
    current_entity_start = -1
    current_entity_end = None

    for entity in entities:
        # Check if the score meets the threshold
        if entity["score"] >= score_threshold:
            # If we're at the start of a new entity or in the middle of one
            if (
                current_entity is None
                or entity["start"] == current_entity_end
                or (
                    entity["start"] == current_entity_end + 1
                    and entity["word"].startswith("▁")
                )
            ):
                # Start a new entity or continue building it
                current_entity = entity["entity"]
                current_entity_score += entity["score"]
                current_entity_text += entity["word"]
                current_entity_end = entity["end"]
                # Set the start position for a new entity
                if current_entity_start == -1:
                    current_entity_start = entity["start"]
            else:
                # We've reached a new entity, so save the previous one
                if current_entity_text != "▁":
                    consecutive_entities.append(current_entity_text)
                # Start a new entity
                current_entity = entity["entity"]
                current_entity_score = entity["score"]
                current_entity_text = entity["word"]
                current_entity_start = entity["start"]
                current_entity_end = entity["end"]
        else:
            # Score threshold not met; reset the current entity
            if current_entity is not None:
                consecutive_entities.append(current_entity_text)
            current_entity = None
            current_entity_score = 0.0
            current_entity_text = ""
            current_entity_start = -1
            current_entity_end = -1

    # Check if the last entity should be added to the list
    if current_entity is not None and current_entity_score >= score_threshold:
        consecutive_entities.append(current_entity_text)

    return consecutive_entities


def partition_names(names):
    partition = (
        []
    )  # List to hold strings containing "・" or "·" with all substrings present in the original list
    rest = []  # List to hold the rest of the strings

    for name in names:
        if "・" in name or "·" in name or "=" in name:
            partition.append(name)

            # Split the name on "・" or "·"
            subnames = name.replace("·", "・").replace("=", "・").split("・")
            # Check if subname is in the original list
            for subname in subnames:
                if (
                    subname in names
                    and subname not in partition
                    and subname not in rest
                ):
                    partition.append(subname)
        elif name not in partition:
            rest.append(name)

    return partition, rest


def is_non_continuous_substring(sub, string):
    it = iter(string)
    return all(char in it for char in sub)


def partition_words(words, max_size):
    # Sort words by length in descending order to handle longer words first
    sorted_words = sorted(words, key=len, reverse=True)

    # Initialize the list of partitions
    partitions = []

    # Helper function to find the right partition for a word
    def find_partition(word):
        for partition in partitions:
            # Check if the word is a substring of any word in the partition
            # or vice versa, and the partition is not full
            if len(partition) < max_size and any(
                is_non_continuous_substring(word, w)
                or is_non_continuous_substring(w, word)
                for w in partition
            ):
                return partition
        return None

    # Iterate over each word and place it in the correct partition
    for word in sorted_words:
        partition = find_partition(word)
        if partition is not None:
            partition.add(word)
        else:
            # If there's no suitable partition, create a new one
            partitions.append({word})

    # Combine partitions where possible
    combined_partitions = []
    while partitions:
        # Take a partition out of the list and try to combine it with others
        current = partitions.pop(0)
        for other in partitions[:]:
            # If they can be combined without exceeding max_size, do so
            if len(current | other) <= max_size:
                current.update(other)
                partitions.remove(other)
        combined_partitions.append(current)

    return combined_partitions


def find_first_non_consecutive_substring(s, string_set):
    def is_subsequence(sub, word):
        # This function checks if sub is a non-consecutive subsequence of word
        it = iter(word)
        return all(c in it for c in sub)

    # Iterate through each word in the set and check for non-consecutive substring
    for word in string_set:
        if is_subsequence(s, word):
            return word
    return None


def flatten(xss):
    return [x for xs in xss for x in xs]


def remove_comments(string):
    lines = string.split("\n")  # Split the string into lines
    result = []
    for line in lines:
        # Check if the line contains "#" or "//"
        if "#" in line:
            line = line[: line.index("#")]  # Remove the part after "#"
        if "//" in line:
            line = line[: line.index("//")]  # Remove the part after "//"
        result.append(line)  # Add the modified line to the result list
    return "\n".join(result)  # Join the lines back into a string


def parse_gpt_json(response):
    response = remove_comments(response)
    start_idx = response.find("{")
    end_idx = response.rfind("}") + 1

    response = response[start_idx:end_idx]
    response = response.replace("'", '"')
    dictionary = json.loads(response)
    return dictionary


def toggle_kana(input_string):
    # Kana Unicode blocks ranges
    HIRAGANA_START = 0x3040
    HIRAGANA_END = 0x309F
    KATAKANA_START = 0x30A0
    KATAKANA_END = 0x30FF
    KANA_GAP = KATAKANA_START - HIRAGANA_START

    toggled_string = ""

    for char in input_string:
        code_point = ord(char)

        # If the character is hiragana, convert to katakana
        if HIRAGANA_START <= code_point <= HIRAGANA_END:
            toggled_string += chr(code_point + KANA_GAP)
        # If the character is katakana, convert to hiragana
        elif KATAKANA_START <= code_point <= KATAKANA_END:
            toggled_string += chr(code_point - KANA_GAP)
        # If it's any other character, leave it as is
        else:
            toggled_string += char

    return toggled_string


def remove_common_suffix(s1, s2):
    # Reverse the strings to compare from the end
    s1_reversed = s1[::-1]
    s2_reversed = s2[::-1]

    # Find the length of the longest common suffix
    common_suffix_length = 0
    for c1, c2 in zip(s1_reversed, s2_reversed):
        if c1 == c2:
            common_suffix_length += 1
        else:
            break

    # Remove the common suffix from both strings
    if common_suffix_length > 0:
        s1 = s1[:-common_suffix_length]
        s2 = s2[:-common_suffix_length]

    return s1, s2


if __name__ == "__main__":
    print(load_config())
    pass
