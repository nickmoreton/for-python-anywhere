from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from wagtail.images import get_image_model
from wagtail.models import Page, Site

from app.blog.models import BlogIndexPage, BlogPostPage
from app.blog.sample_content import SAMPLE_POSTS
from app.blog.sample_images import IMAGE_PALETTES, build_seed_png
from app.home.models import HomePage


class Command(BaseCommand):
    help = "Create or refresh the canonical 20-post Wagtail sample blog."

    @transaction.atomic
    def handle(self, *args, **options):
        homepage = self._get_homepage()
        blog_index, index_created = self._upsert_index(homepage)
        images, images_created = self._upsert_images()
        posts_created, posts_updated = self._upsert_posts(blog_index, images)
        self.stdout.write(
            self.style.SUCCESS(
                f"Blog ready. Index "
                f"{'created' if index_created else 'updated'}. "
                f"Created {images_created} images. "
                f"Created {posts_created} posts. "
                f"Updated {posts_updated} posts."
            )
        )

    def _get_homepage(self):
        try:
            site = Site.objects.get(is_default_site=True)
        except Site.DoesNotExist as error:
            raise CommandError("A default Wagtail site is required.") from error
        except Site.MultipleObjectsReturned as error:
            raise CommandError(
                "Exactly one default Wagtail site is required."
            ) from error
        homepage = site.root_page.specific
        if not isinstance(homepage, HomePage):
            raise CommandError(
                "The default site's root page must be a HomePage."
            )
        return homepage

    def _upsert_index(self, homepage):
        sibling = Page.objects.child_of(homepage).filter(slug="blog").first()
        if sibling and not isinstance(sibling.specific, BlogIndexPage):
            raise CommandError(
                "The /blog/ slug is already used by another page type."
            )
        if sibling:
            blog_index = sibling.specific
            created = False
        else:
            blog_index = BlogIndexPage(title="Blog", slug="blog")
            homepage.add_child(instance=blog_index)
            created = True
        blog_index.title = "Blog"
        blog_index.slug = "blog"
        blog_index.save_revision().publish()
        return blog_index, created

    def _upsert_images(self):
        image_model = get_image_model()
        images = []
        created_count = 0
        for palette_index in range(len(IMAGE_PALETTES)):
            key = f"artwork-{palette_index + 1}"
            title = f"Blog seed: Artwork {palette_index + 1}"
            image = image_model.objects.filter(title=title).first()
            if image is None:
                image = image_model(title=title)
                image.file = build_seed_png(key, title, palette_index)
                image.save()
                created_count += 1
            images.append(image)
        return images, created_count

    def _upsert_posts(self, blog_index, images):
        created_count = 0
        updated_count = 0
        for position, sample in enumerate(SAMPLE_POSTS):
            sibling = (
                Page.objects.child_of(blog_index)
                .filter(slug=sample.slug)
                .first()
            )
            if sibling and not isinstance(sibling.specific, BlogPostPage):
                raise CommandError(
                    f"The seeded slug {sample.slug!r} is used by another "
                    "page type."
                )
            if sibling:
                post = sibling.specific
                updated_count += 1
            else:
                post = BlogPostPage(
                    title=sample.title,
                    slug=sample.slug,
                    date=sample.post_date,
                    author_name=sample.author_name,
                    intro=sample.intro,
                    featured_image=images[position % len(images)],
                    body=sample.stream_data(),
                    search_description=sample.intro,
                )
                blog_index.add_child(instance=post)
                created_count += 1
            post.title = sample.title
            post.slug = sample.slug
            post.date = sample.post_date
            post.author_name = sample.author_name
            post.intro = sample.intro
            post.featured_image = images[position % len(images)]
            post.body = sample.stream_data()
            post.search_description = sample.intro
            post.save_revision().publish()
        return created_count, updated_count
