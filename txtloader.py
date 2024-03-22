import argparse
import re
from tqdm import tqdm
from loguru import logger
from translate import translate, validate, SqlWrapper
from utils import load_config


def main():
    config = load_config()
    logger.add(f"output/{config['CN_TITLE']}/info.log", colorize=True, level="DEBUG")
    parser = argparse.ArgumentParser()
    parser.add_argument("--dryrun", action="store_true")
    args = parser.parse_args()
    
    if args.dryrun:
        logger.warning("Dry run mode enabled. No translation will be performed.")

    with open(f"output/{config['CN_TITLE']}/input.txt", "r", encoding="utf-8") as file:
        content = file.read()

    paragraphs = re.split(r"[。.]", content)
    translated_paragraphs = []

    with SqlWrapper(f"output/{config['CN_TITLE']}/buffer.db") as buffer:
        group = ""
        for paragraph in tqdm(paragraphs):
            group += paragraph + "。"
            if len(group) > 1000 or paragraph == paragraphs[-1]:
                if group in buffer and validate(group, buffer[group]):
                    translated_group = buffer[group]
                else:
                    translated_group = translate(group, dryrun=args.dryrun)
                    if not args.dryrun:
                        buffer[group] = translated_group
                translated_paragraphs.append(translated_group)
                group = ""

    with open(f"output/{config['CN_TITLE']}/output.txt", "w", encoding="utf-8") as file:
        file.write("\n".join(translated_paragraphs))


if __name__ == "__main__":
    main()
