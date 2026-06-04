from pathlib import Path

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Field, Layout, Submit
from django import forms
from django.conf import settings

from .methods import get_next_state, is_mediacms_editor
from .models import MEDIA_STATES, Category, Media, MediaPermission, Subtitle
from .waic_categories import waic_fixed_category_queryset
from .widgets import CategoryModalWidget

_PUBLISH_STATE_HTML = (Path(__file__).parent.parent / 'templates/cms/partials/media_publish_state.html').read_text()


class CustomField(Field):
    template = 'cms/crispy_custom_field.html'


class MultipleSelect(forms.CheckboxSelectMultiple):
    input_type = "checkbox"


class MediaMetadataForm(forms.ModelForm):
    new_tags = forms.CharField(label="标签", help_text="用逗号分隔的标签列表", required=False)

    class Meta:
        model = Media
        fields = (
            "friendly_token",
            "title",
            "new_tags",
            "add_date",
            "uploaded_poster",
            "description",
            "enable_comments",
            "thumbnail_time",
            "is_important",
        )

        widgets = {
            "new_tags": MultipleSelect(),
            "description": forms.Textarea(attrs={'rows': 4}),
            "add_date": forms.DateTimeInput(attrs={'type': 'datetime-local', 'step': '1'}, format='%Y-%m-%dT%H:%M:%S'),
            "thumbnail_time": forms.NumberInput(attrs={'min': 0, 'step': 0.1}),
        }
        labels = {
            "friendly_token": "URL 别名",
            "title": "标题",
            "add_date": "发布日期",
            "description": "描述",
            "enable_comments": "允许评论",
            "uploaded_poster": "封面图片",
            "thumbnail_time": "缩略图时间（秒）",
            "is_important": "标记为重要",
        }
        help_texts = {
            "title": "",
            "friendly_token": "媒体链接的自定义短标识",
            "thumbnail_time": "设置视频缩略图的截取时间（秒）",
            "uploaded_poster": "最大文件大小: 5MB",
            "description": "",
            "enable_comments": "是否允许用户对该媒体发表评论",
            "is_important": "标记为重要后将向所有用户发送通知",
        }

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super(MediaMetadataForm, self).__init__(*args, **kwargs)
        if not getattr(settings, 'ALLOW_CUSTOM_MEDIA_URLS', False):
            self.fields.pop("friendly_token")
        if self.instance.media_type != "video":
            self.fields.pop("thumbnail_time")
        if self.instance.media_type == "image":
            self.fields.pop("uploaded_poster")

        self.fields["new_tags"].initial = ", ".join([tag.title for tag in self.instance.tags.all()])

        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_class = 'post-form'
        self.helper.form_method = 'post'
        self.helper.form_enctype = "multipart/form-data"
        self.helper.form_show_errors = False

        layout_fields = [
            CustomField('title'),
            CustomField('new_tags'),
            CustomField('add_date'),
            CustomField('description'),
            CustomField('enable_comments'),
        ]
        if self.instance.media_type != "image":
            layout_fields.append(CustomField('uploaded_poster'))

        self.helper.layout = Layout(*layout_fields)

        if self.instance.media_type == "video":
            self.helper.layout.append(CustomField('thumbnail_time'))
        if is_mediacms_editor(self.user):
            self.helper.layout.append(CustomField('is_important'))
        if getattr(settings, 'ALLOW_CUSTOM_MEDIA_URLS', False):
            self.helper.layout.insert(0, CustomField('friendly_token'))

        self.helper.layout.append(FormActions(Submit('submit', '保存修改', css_class='primaryAction')))

    def clean_friendly_token(self):
        token = self.cleaned_data.get("friendly_token", "").strip()

        if token:
            if not all(c.isalnum() or c in "-_" for c in token):
                raise forms.ValidationError("Slug can only contain alphanumeric characters, underscores, or hyphens.")

            if Media.objects.filter(friendly_token=token).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("This slug is already in use. Please choose a different one.")
            return token

    def clean_uploaded_poster(self):
        image = self.cleaned_data.get("uploaded_poster", False)
        if image:
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Image file too large ( > 5mb )")
            return image

    def save(self, *args, **kwargs):
        data = self.cleaned_data  # noqa

        media = super(MediaMetadataForm, self).save(*args, **kwargs)
        return media


class MediaPublishForm(forms.ModelForm):
    confirm_state = forms.BooleanField(required=False, initial=False, label="Acknowledge sharing status", help_text="")
    shared = forms.BooleanField(required=False, initial=False, label="Shared")

    class Meta:
        model = Media
        fields = ("category", "state", "featured", "reported_times", "is_reviewed", "allow_download")

        widgets = {
            "category": CategoryModalWidget(),
            "state": forms.RadioSelect(),
        }

    def __init__(self, user, *args, **kwargs):
        self.user = user
        self.request = kwargs.pop('request', None)
        super(MediaPublishForm, self).__init__(*args, **kwargs)

        self.was_shared = self.instance.is_shared if self.instance.pk else False
        self.had_explicit_permission = self.instance.permissions.exists() if self.instance.pk else False
        is_embed_mode = self._check_embed_mode()
        self.fields['category'].queryset = waic_fixed_category_queryset()

        self.fields["featured"].label = "精选"
        self.fields["featured"].help_text = "由管理员设为全站精选内容"
        self.fields["reported_times"].label = "被举报次数"
        self.fields["reported_times"].help_text = "该媒体被举报的次数"
        self.fields["is_reviewed"].label = "已审核"
        self.fields["is_reviewed"].help_text = "审核通过后可在公开列表中显示"
        self.fields["allow_download"].label = "允许下载"
        self.fields["allow_download"].help_text = "是否显示下载按钮"
        self.fields["shared"].label = "共享"
        self.fields["category"].label = "分类"
        self.fields["category"].help_text = "媒体可归入一个或多个分类"
        self.fields["confirm_state"].label = "确认共享状态变更"

        self.fields["shared"].initial = self.was_shared
        self.initial["shared"] = self.was_shared

        if not is_mediacms_editor(user):
            for field in ["featured", "reported_times", "is_reviewed"]:
                self.fields[field].disabled = True
                self.fields[field].widget.attrs['class'] = 'read-only-field'
                self.fields[field].widget.attrs['title'] = "This field can only be modified by MediaCMS admins or editors"

            if settings.PORTAL_WORKFLOW not in ["public"]:
                valid_states = ["unlisted", "private"]
                if self.instance.state and self.instance.state not in valid_states:
                    valid_states.append(self.instance.state)
                self.fields["state"].choices = [(state, dict(MEDIA_STATES).get(state, state)) for state in valid_states]

        if getattr(settings, 'USE_RBAC', False) and 'category' in self.fields:
            if is_mediacms_editor(user):
                pass
            else:
                self.fields['category'].initial = self.instance.category.all()

                non_rbac_categories = waic_fixed_category_queryset().filter(is_rbac_category=False)
                rbac_categories = user.get_rbac_categories_as_contributor()
                combined_category_ids = list(non_rbac_categories.values_list('id', flat=True)) + list(rbac_categories.values_list('id', flat=True))

                if self.instance.pk:
                    instance_category_ids = list(self.instance.category.all().values_list('id', flat=True))
                    combined_category_ids = list(set(combined_category_ids + instance_category_ids))

                self.fields['category'].queryset = Category.objects.filter(id__in=combined_category_ids).order_by('title')

        # Filter for LMS courses only when in embed mode
        if is_embed_mode and 'category' in self.fields:
            current_queryset = self.fields['category'].queryset
            self.fields['category'].queryset = current_queryset.filter(is_lms_course=True)
            self.fields['category'].label = 'Course'
            self.fields['category'].help_text = 'Media can be shared with one or more courses'
            self.fields['category'].widget.is_lms_mode = True

        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_class = 'post-form'
        self.helper.form_method = 'post'
        self.helper.form_enctype = "multipart/form-data"
        self.helper.form_show_errors = False
        self.helper.layout = Layout(
            CustomField('category'),
            HTML(_PUBLISH_STATE_HTML),
            CustomField('featured'),
            CustomField('reported_times'),
            CustomField('is_reviewed'),
            CustomField('allow_download'),
        )

        self.helper.layout.append(FormActions(Submit('submit', '发布', css_class='primaryAction')))

    def _check_embed_mode(self):
        """Check if the current request is in embed mode"""
        if not self.request:
            return False

        # Check query parameter
        mode = self.request.GET.get('mode', '')
        if mode == 'lms_embed_mode':
            return True

        # Check session storage
        if self.request.session.get('lms_embed_mode') == 'true':
            return True

        return False

    def clean(self):
        cleaned_data = super().clean()
        shared = cleaned_data.get("shared")

        if self.was_shared and not shared and not cleaned_data.get('confirm_state'):
            self.add_error('confirm_state', "I understand that unchecking Shared will remove all existing sharing for this media.")

        return cleaned_data

    def save(self, *args, **kwargs):
        data = self.cleaned_data
        state = data.get("state")
        shared = data.get("shared")

        if shared:
            if self.request:
                submitted_categories = self.cleaned_data.get('category', [])
                submitted_has_rbac = any(cat.is_rbac_category for cat in submitted_categories)
                if self.had_explicit_permission or (not self.was_shared and not submitted_has_rbac):
                    MediaPermission.objects.get_or_create(
                        media=self.instance,
                        user=self.request.user,
                        defaults={'owner_user': self.request.user, 'permission': 'owner'},
                    )
        elif not shared:
            self.instance.permissions.all().delete()
            rbac_cats = self.instance.category.filter(is_rbac_category=True)
            self.instance.category.remove(*rbac_cats)

        if state != self.initial.get("state"):
            self.instance.state = get_next_state(self.user, self.initial.get("state"), self.instance.state)

        media = super(MediaPublishForm, self).save(*args, **kwargs)

        return media


class WhisperSubtitlesForm(forms.ModelForm):
    class Meta:
        model = Media
        fields = (
            "allow_whisper_transcribe",
            "allow_whisper_transcribe_and_translate",
        )
        labels = {
            "allow_whisper_transcribe": "语音转文字",
            "allow_whisper_transcribe_and_translate": "英文翻译",
        }
        help_texts = {
            "allow_whisper_transcribe": "使用本地 Whisper 模型自动生成字幕",
            "allow_whisper_transcribe_and_translate": "同时生成英文字幕翻译",
        }

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super(WhisperSubtitlesForm, self).__init__(*args, **kwargs)

        if self.instance.allow_whisper_transcribe:
            self.fields['allow_whisper_transcribe'].widget.attrs['readonly'] = True
            self.fields['allow_whisper_transcribe'].widget.attrs['disabled'] = True
        if self.instance.allow_whisper_transcribe_and_translate:
            self.fields['allow_whisper_transcribe_and_translate'].widget.attrs['readonly'] = True
            self.fields['allow_whisper_transcribe_and_translate'].widget.attrs['disabled'] = True

        both_readonly = self.instance.allow_whisper_transcribe and self.instance.allow_whisper_transcribe_and_translate

        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_class = 'post-form'
        self.helper.form_method = 'post'
        self.helper.form_enctype = "multipart/form-data"
        self.helper.form_show_errors = False
        self.helper.layout = Layout(
            CustomField('allow_whisper_transcribe'),
            CustomField('allow_whisper_transcribe_and_translate'),
        )

        if not both_readonly:
            self.helper.layout.append(FormActions(Submit('submit_whisper', '提交', css_class='primaryAction')))
        else:
            # Optional: Add a disabled button with explanatory text
            self.helper.layout.append(
                FormActions(Submit('submit_whisper', '提交', css_class='primaryAction', disabled=True), HTML('<small class="text-muted">两个选项都已启用，无法重复提交</small>'))
            )

    def clean_allow_whisper_transcribe(self):
        # Ensure the field value doesn't change if it was originally True
        if self.instance and self.instance.allow_whisper_transcribe:
            return self.instance.allow_whisper_transcribe
        return self.cleaned_data['allow_whisper_transcribe']

    def clean_allow_whisper_transcribe_and_translate(self):
        # Ensure the field value doesn't change if it was originally True
        if self.instance and self.instance.allow_whisper_transcribe_and_translate:
            return self.instance.allow_whisper_transcribe_and_translate
        return self.cleaned_data['allow_whisper_transcribe_and_translate']


class SubtitleForm(forms.ModelForm):
    class Meta:
        model = Subtitle
        fields = ["language", "subtitle_file"]

        labels = {
            "subtitle_file": "上传字幕文件",
            "language": "语言",
        }
        help_texts = {
            "subtitle_file": "支持 SubRip (.srt) 和 WebVTT (.vtt) 格式",
        }

    def __init__(self, media_item, *args, **kwargs):
        super(SubtitleForm, self).__init__(*args, **kwargs)
        self.instance.media = media_item

        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_class = 'post-form'
        self.helper.form_method = 'post'
        self.helper.form_enctype = "multipart/form-data"
        self.helper.form_show_errors = False
        self.helper.layout = Layout(
            CustomField('subtitle_file'),
            CustomField('language'),
        )

        self.helper.layout.append(FormActions(Submit('submit', '提交', css_class='primaryAction')))

    def save(self, *args, **kwargs):
        self.instance.user = self.instance.media.user
        media = super(SubtitleForm, self).save(*args, **kwargs)
        return media


class EditSubtitleForm(forms.Form):
    subtitle = forms.CharField(widget=forms.Textarea, required=True)

    def __init__(self, subtitle, *args, **kwargs):
        super(EditSubtitleForm, self).__init__(*args, **kwargs)
        self.fields["subtitle"].initial = subtitle.subtitle_file.read().decode("utf-8")


class ContactForm(forms.Form):
    from_email = forms.EmailField(required=True)
    name = forms.CharField(required=False)
    message = forms.CharField(widget=forms.Textarea, required=True)

    def __init__(self, user, *args, **kwargs):
        super(ContactForm, self).__init__(*args, **kwargs)
        self.fields["name"].label = "Your name:"
        self.fields["from_email"].label = "Your email:"
        self.fields["message"].label = "Please add your message here and submit:"
        self.user = user
        if user.is_authenticated:
            self.fields.pop("name")
            self.fields.pop("from_email")


class ReplaceMediaForm(forms.Form):
    new_media_file = forms.FileField(
        required=True,
        label="New Media File",
        help_text="Select a new file to replace the current media",
    )

    def __init__(self, media_instance, *args, **kwargs):
        self.media_instance = media_instance
        super(ReplaceMediaForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_tag = True
        self.helper.form_class = 'post-form'
        self.helper.form_method = 'post'
        self.helper.form_enctype = "multipart/form-data"
        self.helper.form_show_errors = False
        self.helper.layout = Layout(
            CustomField('new_media_file'),
        )

        self.helper.layout.append(FormActions(Submit('submit', 'Replace Media', css_class='primaryAction')))

    def clean_new_media_file(self):
        file = self.cleaned_data.get("new_media_file", False)
        if file:
            if file.size > settings.UPLOAD_MAX_SIZE:
                max_size_mb = settings.UPLOAD_MAX_SIZE / (1024 * 1024)
                raise forms.ValidationError(f"File too large. Maximum size: {max_size_mb:.0f}MB")
            return file
