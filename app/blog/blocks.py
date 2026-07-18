from wagtail import blocks


class QuoteBlock(blocks.StructBlock):
    text = blocks.TextBlock(required=True)
    attribution = blocks.CharBlock(required=False, max_length=120)

    class Meta:
        icon = "openquote"
        template = "blog/blocks/quote.html"


class CodeBlock(blocks.StructBlock):
    language = blocks.CharBlock(required=False, max_length=40)
    code = blocks.TextBlock(required=True)

    class Meta:
        icon = "code"
        template = "blog/blocks/code.html"
