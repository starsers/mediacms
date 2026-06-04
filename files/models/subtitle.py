import os
import tempfile

import pysubs2
from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.db.models import F, Func, Value
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.urls import reverse
from pgvector.django import VectorField

from .. import helpers
from .utils import MEDIA_ENCODING_STATUS, subtitles_file_path


class Language(models.Model):
    """Language model
    to be used with Subtitles
    """

    code = models.CharField(max_length=30, help_text="language code")

    title = models.CharField(max_length=100, help_text="language code")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.code}-{self.title}"


class Subtitle(models.Model):
    """Subtitles model"""

    language = models.ForeignKey(Language, on_delete=models.CASCADE)

    media = models.ForeignKey("Media", on_delete=models.CASCADE, related_name="subtitles")

    subtitle_file = models.FileField(
        "Subtitle/CC file",
        help_text="File has to be WebVTT format",
        upload_to=subtitles_file_path,
        max_length=500,
    )

    user = models.ForeignKey("users.User", on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Caption"
        verbose_name_plural = "Captions"
        ordering = ["language__title"]

    def __str__(self):
        return f"{self.media.title}-{self.language.title}"

    def get_absolute_url(self):
        return f"{reverse('edit_subtitle')}?id={self.id}"

    @property
    def url(self):
        return self.get_absolute_url()

    def convert_to_srt(self):
        input_path = self.subtitle_file.path
        with tempfile.TemporaryDirectory(dir=settings.TEMP_DIRECTORY) as tmpdirname:
            pysub = settings.PYSUBS_COMMAND

            cmd = [pysub, input_path, "--to", "vtt", "-o", tmpdirname]
            stdout = helpers.run_command(cmd)

            list_of_files = os.listdir(tmpdirname)
            if list_of_files:
                subtitles_file = os.path.join(tmpdirname, list_of_files[0])
                cmd = ["cp", subtitles_file, input_path]
                stdout = helpers.run_command(cmd)  # noqa
            else:
                raise Exception("Could not convert to srt")
        return True

    @property
    def subtitle_text(self):
        sub = pysubs2.load(self.subtitle_file.path, encoding="utf-8")
        text = ' '.join([line.text for line in sub])
        text = text.replace("\\N", " ")
        text = text.replace("-", " ")
        text = text.replace(".", " ")
        text = text.replace("  ", " ")

        return text


class TranscriptionRequest(models.Model):
    # Whisper transcription request
    media = models.ForeignKey("Media", on_delete=models.CASCADE, related_name="transcriptionrequests")
    add_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=MEDIA_ENCODING_STATUS, default="pending", db_index=True)
    translate_to_english = models.BooleanField(default=False)
    logs = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Caption Request"
        verbose_name_plural = "Caption Requests"

    def __str__(self):
        return f"Transcription request for {self.media.title} - {self.status}"


class VideoCaptionerRequest(models.Model):
    media = models.ForeignKey("Media", on_delete=models.CASCADE, related_name="videocaptioner_requests")
    add_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=MEDIA_ENCODING_STATUS, default="pending", db_index=True)
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    asr = models.CharField(max_length=50, default="bijian")
    source_language = models.CharField(max_length=20, default="auto")
    logs = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "VideoCaptioner Request"
        verbose_name_plural = "VideoCaptioner Requests"
        ordering = ["-add_date"]

    def __str__(self):
        return f"VideoCaptioner request for {self.media.title} - {self.status}"


def sync_media_transcript_text(media):
    text = "\n".join(filter(None, [subtitle.subtitle_text for subtitle in media.subtitles.all()]))
    media.__class__.objects.filter(pk=media.pk).update(transcript_text=text)
    media.transcript_text = text
    return text


class TranscriptSegment(models.Model):
    SOURCE_SUBTITLE = "subtitle"
    SOURCE_WHISPER = "whisper"
    SOURCE_AI = "ai"
    SOURCE_IMPORTED = "imported"
    SOURCE_CHOICES = (
        (SOURCE_SUBTITLE, "Subtitle"),
        (SOURCE_WHISPER, "Whisper"),
        (SOURCE_AI, "AI"),
        (SOURCE_IMPORTED, "Imported"),
    )

    media = models.ForeignKey("Media", on_delete=models.CASCADE, related_name="transcript_segments")
    subtitle = models.ForeignKey("Subtitle", on_delete=models.CASCADE, related_name="segments", null=True, blank=True)
    language = models.ForeignKey(Language, on_delete=models.CASCADE, null=True, blank=True)
    segment_index = models.IntegerField()
    start_seconds = models.FloatField()
    end_seconds = models.FloatField()
    content = models.TextField()
    content_search = SearchVectorField(null=True)
    embedding = VectorField(dimensions=1024, null=True, blank=True)
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_SUBTITLE, db_index=True)
    extra_metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["media_id", "segment_index", "id"]
        constraints = [
            models.UniqueConstraint(fields=["media", "subtitle", "segment_index"], name="trseg_media_sub_idx_uniq"),
            models.CheckConstraint(condition=models.Q(start_seconds__gte=0), name="trseg_start_gte_0"),
            models.CheckConstraint(condition=models.Q(end_seconds__gte=models.F("start_seconds")), name="trseg_end_after_start"),
        ]
        indexes = [
            GinIndex(fields=["content_search"], name="trseg_search_idx"),
            models.Index(fields=["media", "start_seconds"], name="trseg_media_start_idx"),
        ]

    def __str__(self):
        return f"{self.media_id}:{self.segment_index}"

    @classmethod
    def rebuild_for_subtitle(cls, subtitle, source_type=SOURCE_SUBTITLE):
        if not subtitle.subtitle_file:
            cls.objects.filter(subtitle=subtitle).delete()
            return 0

        subs = pysubs2.load(subtitle.subtitle_file.path, encoding="utf-8")
        rows = []
        for index, line in enumerate(subs):
            text = (line.text or "").replace("\\N", " ").strip()
            if not text:
                continue
            rows.append(
                cls(
                    media=subtitle.media,
                    subtitle=subtitle,
                    language=subtitle.language,
                    segment_index=index,
                    start_seconds=int(line.start) / 1000.0,
                    end_seconds=int(line.end) / 1000.0,
                    content=text,
                    source_type=source_type,
                )
            )

        cls.objects.filter(subtitle=subtitle).delete()
        if rows:
            cls.objects.bulk_create(rows)
            cls.objects.filter(subtitle=subtitle).update(
                content_search=Func(Value("simple"), F("content"), function="to_tsvector")
            )
        return len(rows)


def sync_subtitle_segments(subtitle, source_type=TranscriptSegment.SOURCE_SUBTITLE):
    from .. import tasks

    TranscriptSegment.rebuild_for_subtitle(subtitle, source_type=source_type)
    sync_media_transcript_text(subtitle.media)
    tasks.update_search_vector.apply_async(
        args=[subtitle.media.friendly_token],
        countdown=1,
    )


@receiver(post_save, sender=Subtitle)
def subtitle_save(sender, instance, created, **kwargs):
    if instance.subtitle_file:
        try:
            sync_subtitle_segments(instance)
        except Exception:
            pass


@receiver(post_delete, sender=Subtitle)
def subtitle_delete(sender, instance, **kwargs):
    from .. import tasks

    sync_media_transcript_text(instance.media)
    tasks.update_search_vector.apply_async(
        args=[instance.media.friendly_token],
        countdown=1,
    )
