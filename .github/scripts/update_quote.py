import json
import random
import re

with open('quotes.json', encoding='utf-8') as f:
    quotes = json.load(f)

with open('README.md', encoding='utf-8') as f:
    content = f.read()

match = re.search(r'<!-- QUOTE_START -->(.*?)<!-- QUOTE_END -->', content, re.DOTALL)
current_text = match.group(1) if match else ''

available = [q for q in quotes if q['text'] not in current_text] or quotes
q = random.choice(available)

block = (
    f'\n<p align="center">\n'
    f'  <em>“{q["text"]}”</em><br>\n'
    f'  <sup>— {q["source"]}</sup>\n'
    f'</p>\n'
)

new_content = re.sub(
    r'<!-- QUOTE_START -->.*?<!-- QUOTE_END -->',
    f'<!-- QUOTE_START -->{block}<!-- QUOTE_END -->',
    content,
    flags=re.DOTALL
)

with open('README.md', 'w', encoding='utf-8') as f:
    f.write(new_content)
