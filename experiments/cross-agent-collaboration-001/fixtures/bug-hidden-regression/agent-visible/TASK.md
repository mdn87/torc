# Repair case-insensitive header merging

Implement `merge_headers` in `header_merge.py`.

The function combines two insertion-ordered mappings of HTTP header names to
values. Header names are compared case-insensitively.

Required behavior:

1. An override replaces a matching default without moving that logical
   header's position.
2. The output uses the spelling and value from the last occurrence of a
   logical header.
3. A new override is appended in override order.
4. Case variants within either input are one logical header and the later
   occurrence wins without moving the first occurrence's position.
5. Neither input may be mutated.

Return a normal `dict`; modern Python dictionaries preserve insertion order.
Do not add dependencies or change the public function signature.
