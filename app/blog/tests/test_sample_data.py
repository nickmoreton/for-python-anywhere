from django.test import SimpleTestCase

from PIL import Image

from app.blog.sample_content import SAMPLE_POSTS
from app.blog.sample_images import IMAGE_PALETTES, build_seed_png


class SampleContentTests(SimpleTestCase):
    def test_sample_posts_are_complete_and_unique(self):
        self.assertEqual(len(SAMPLE_POSTS), 20)
        self.assertEqual(len({post.slug for post in SAMPLE_POSTS}), 20)
        self.assertTrue(
            all(
                post.title and post.intro and post.author_name
                for post in SAMPLE_POSTS
            )
        )
        self.assertTrue(all(len(post.facts) >= 2 for post in SAMPLE_POSTS))

    def test_stream_data_uses_only_supported_blocks(self):
        approved_blocks = {
            "heading",
            "paragraph",
            "bulleted_list",
            "quote",
            "code",
        }

        for post in SAMPLE_POSTS:
            block_names = {name for name, _value in post.stream_data()}
            self.assertLessEqual(block_names, approved_blocks)

    def test_generated_png_is_deterministic_and_valid(self):
        first = build_seed_png(
            "page-tree",
            "Understanding the page tree",
            0,
        )
        second = build_seed_png(
            "page-tree",
            "Understanding the page tree",
            0,
        )

        self.assertEqual(first.name, "blog-seed-page-tree.png")
        self.assertEqual(first.read(), second.read())
        first.seek(0)
        with Image.open(first) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.size, (1200, 720))

    def test_artwork_has_multiple_palettes(self):
        self.assertEqual(len(IMAGE_PALETTES), 5)
