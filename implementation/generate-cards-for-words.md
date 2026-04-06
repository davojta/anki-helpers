## feature: generate examples for the words

### similar
Use get_examples_for_red_flags_cards implementation as base

### input
input is the path to the words.md file with words in finnish language which we need to generate cards for

input paraments - topics for which we need to generate examples, default - well-being,nature,artificial intelligence

### output
examples-table.md with markdown table with columns
- the word in nominative case
- translation to english
- 2-3 synonyms in Simple Finnish
- example with word in Simple Finnish
- translation of sentence to English

### prompt used to generate data

f"""I'm learning finnish language on level A2.
Please generate 5 example sentences for each words provided below with translation to english.
- one simple and short sentence (near 7 words)
- one medium (7-12 words) length sentence on theme of AI
- one medium (7-12 words) length sentence on theme of well-being
- one medium (7-12 words) length sentence on theme of ecology and responsible consumption
- one medium (7-12 words) length sentence on theme of cycling as a hobby in finland
  Words:
  {words_content}"""
