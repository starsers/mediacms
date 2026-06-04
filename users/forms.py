from django import forms
from django.conf import settings

from files.methods import is_mediacms_manager

from .models import Channel, User


class SignupForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        label="姓名",
        widget=forms.TextInput(attrs={"placeholder": "姓名"}),
    )

    def signup(self, request, user):
        user.name = self.cleaned_data["name"]
        user.save()


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "name",
            "description",
            "logo",
            "notification_on_comments",
            "is_featured",
            "advancedUser",
            "is_manager",
            "is_editor",
            "is_approved",
            # "allow_contact",
        )
        labels = {
            "name": "姓名",
            "description": "简介",
            "logo": "头像",
            "notification_on_comments": "接收评论通知",
            "advancedUser": "高级用户",
            "is_manager": "管理员",
            "is_editor": "编辑者",
            "is_approved": "已批准",
        }

    def clean_logo(self):
        image = self.cleaned_data.get("logo", False)
        if image:
            if image.size > 2 * 1024 * 1024:
                raise forms.ValidationError("图片文件过大（超过 2MB）")
            return image
        else:
            raise forms.ValidationError("请提供头像")

    def __init__(self, user, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        self.fields.pop("is_featured")
        if not is_mediacms_manager(user):
            self.fields.pop("advancedUser")
            self.fields.pop("is_manager")
            self.fields.pop("is_editor")

        if not settings.USERS_NEEDS_TO_BE_APPROVED or not is_mediacms_manager(user):
            if "is_approved" in self.fields:
                self.fields.pop("is_approved")

        if user.socialaccount_set.exists():
            # for Social Accounts do not allow to edit the name
            self.fields["name"].widget.attrs['readonly'] = True


class ChannelForm(forms.ModelForm):
    class Meta:
        model = Channel
        fields = ("banner_logo",)

    def clean_banner_logo(self):
        image = self.cleaned_data.get("banner_logo", False)
        if image:
            if image.size > 2 * 1024 * 1024:
                raise forms.ValidationError("Image file too large ( > 2mb )")
            return image
        else:
            raise forms.ValidationError("Please provide a banner")
