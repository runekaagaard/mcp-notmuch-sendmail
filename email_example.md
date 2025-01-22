# Markdown Formatting Test Document
*Last updated: January 19, 2025*

## Text Formatting

This paragraph demonstrates **bold text**, *italic text*, and ***bold italic text***. You can also use _underscores_ for emphasis.

Here's some `inline code` and ~~strikethrough text~~.

## Lists

### Unordered Lists
* Basic item
* Item with *emphasis*
  * Nested item 1
  * Nested item 2
    * Deep nested item
* Back to level 1

### Ordered Lists
1. First item
2. Second item
   1. Nested numbered item
   2. Another nested item
      * Mixed list type
      * Another bullet
3. Back to main numbering

## Links and References

* [External Link](https://example.com)
* [Link with Title](https://example.com "Hover text")
* [Reference Link][ref1]
* <https://raw-url.com>
* <example@email.com>

[ref1]: https://reference-style-link.com

## Images

Here's an two images, side by side:

![Test Image](test.png "Image tooltip")
![Test Image](test.png "Image tooltip")

## Blockquotes

> Single line quote

> Multi-line quote
> with continuation
>> Nested quote

## Code Blocks

Inline: `const x = 42;`

Fenced with syntax highlighting:
```python
def hello_world():
    print("Hello, World!")
    return True
```

```css
.markdown-body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 16px;
    line-height: 1.5;
    word-wrap: break-word;
}
```

## Tables

| Left | Center | Right |
|:-----|:------:|------:|
|Col 1 | Col 2  | Col 3 |
|Long cell| Short | *Italic* |
|**Bold**| `code` | [Link](url) |

## Definition Lists

HTML
:   The standard markup language for documents designed to be displayed in a web browser.

CSS
:   A style sheet language used for describing the presentation of a document written in HTML or XML.

## Task Lists

- [x] Completed task
- [ ] Incomplete task
- [ ] Foo
- [x] Bar

## Footnotes

Here's a sentence with a footnote[^1].

[^1]: This is the footnote content.

## HTML Elements

<div class="custom-class">
  <p>Custom HTML with <span style="color: red;">colored text</span></p>
</div>

## Horizontal Rules

A: \-\-\-

---

B: \*\*\*

***

C: \_\_\_

___

## Escaping Characters

\*Not italic\*  
\`Not code\`  
\[Not a link\]  
\{Not a template\}  

## The End
