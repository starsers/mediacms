from django.db import migrations


WAIC_FIXED_CATEGORY_TITLES = (
    "会务文档",
    "嘉宾资料",
    "大会影片",
    "大会活动",
    "大会电视",
    "大会视觉",
    "大会音乐",
    "实验影像",
    "宣传素材",
    "技术资料",
    "纪录片",
)


def ensure_fixed_categories(apps, schema_editor):
    Category = apps.get_model("files", "Category")
    for title in WAIC_FIXED_CATEGORY_TITLES:
        category = Category.objects.filter(title=title).order_by("id").first()
        if category is None:
            Category.objects.create(title=title, is_global=True)
        elif not category.is_global:
            category.is_global = True
            category.save(update_fields=["is_global"])


class Migration(migrations.Migration):
    dependencies = [
        ("files", "0028_alter_media_approval_status_alter_media_is_reviewed"),
    ]

    operations = [
        migrations.RunPython(ensure_fixed_categories, migrations.RunPython.noop),
    ]
