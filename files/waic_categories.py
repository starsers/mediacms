from django.db.models import Case, IntegerField, Value, When


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


def fixed_category_ordering():
    return Case(
        *[
            When(title=title, then=Value(index))
            for index, title in enumerate(WAIC_FIXED_CATEGORY_TITLES)
        ],
        default=Value(len(WAIC_FIXED_CATEGORY_TITLES)),
        output_field=IntegerField(),
    )


def ensure_waic_fixed_categories():
    from .models import Category

    categories = []
    for title in WAIC_FIXED_CATEGORY_TITLES:
        category = Category.objects.filter(title=title).order_by("id").first()
        if category is None:
            category = Category.objects.create(title=title, is_global=True)
        elif not category.is_global:
            category.is_global = True
            category.save(update_fields=["is_global"])
        categories.append(category)
    return categories


def waic_fixed_category_queryset():
    from .models import Category

    ensure_waic_fixed_categories()
    return Category.objects.filter(
        title__in=WAIC_FIXED_CATEGORY_TITLES,
        is_lms_course=False,
    ).order_by(fixed_category_ordering(), "title", "id")


def waic_fixed_category_options():
    return [
        {"uid": str(category.uid), "title": category.title}
        for category in waic_fixed_category_queryset()
    ]


def get_waic_fixed_category(category_uid=None, title=None):
    from .models import Category

    ensure_waic_fixed_categories()
    queryset = Category.objects.filter(title__in=WAIC_FIXED_CATEGORY_TITLES)
    if category_uid:
        return queryset.filter(uid=category_uid).first()
    if title:
        return queryset.filter(title=title).order_by("id").first()
    return None
