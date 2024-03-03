from translate import align_translate, SqlWrapper
from utils import load_config
from loguru import logger
import re
import argparse


# Load the configuration
config = load_config()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dryrun", action="store_true")
    args = parser.parse_args()
    
    if args.dryrun:
        logger.warning("Dry run mode enabled. No translation will be performed.")
    
    # Open the document
    with open(f"output/{config['CN_TITLE']}/input.srt", "rb") as f:
        srt = f.read().decode("utf-8")
    
    # Parse srt by removing the time stamps
    subtitles = re.sub(r"\[.* --> .*\]", "", srt)
    subtitles = [subtitle.strip() for subtitle in subtitles.split("\n")]
    
    with SqlWrapper(f"output/{config['CN_TITLE']}/buffer.db") as buffer:
        align_translate(subtitles, buffer, args.dryrun)

        # Replace original subtitles with translated subtitles
        cn_results = []
        cnen_results = []
        for line in srt.split("\n"):
            subtitle = re.sub(r"\[.* --> .*\]", "", line).strip()
            if subtitle == '' or subtitle not in buffer:
                cn_results.append(line)
                cnen_results.append(line)
            else:
                cn_results.append(line.replace(subtitle, buffer[subtitle]))
                cnen_results.append(line.replace(subtitle, subtitle + " | " + buffer[subtitle]))
        
        with open(f"output/{config['CN_TITLE']}/{config['CN_TITLE']}_cn.srt", "w", encoding="utf-8") as f:
            f.write("".join(cn_results))
        with open(f"output/{config['CN_TITLE']}/{config['CN_TITLE']}_cnen.srt", "w", encoding="utf-8") as f:
            f.write("".join(cnen_results))
