from rest_framework import serializers
from ..models.engine import Asset, ContentUnit
from ..models.course import Course
from ..utils import get_translation


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ['id', 'slug', 'title', 'source_language', 'target_language', 'description_ky', 'cefr_min', 'cefr_max']


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ['id', 'asset_type', 'file', 'duration_ms', 'metadata']


class ContentUnitSerializer(serializers.ModelSerializer):
    primary_audio = AssetSerializer(read_only=True)
    primary_image = AssetSerializer(read_only=True)
    text = serializers.SerializerMethodField()
    meaning = serializers.SerializerMethodField()

    class Meta:
        model = ContentUnit
        fields = ['id', 'unit_type', 'text', 'meaning', 'primary_audio', 'primary_image']

    def get_text(self, obj):
        lang = self.context.get('lang', 'en')
        return get_translation(obj.text_group, lang, obj.text)

    def get_meaning(self, obj):
        lang = self.context.get('lang', 'en')
        return get_translation(obj.meaning_group, lang, obj.meaning)
