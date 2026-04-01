from rest_framework import viewsets, status, mixins
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError
from ..models import SpeechSubmission
from ..serializers import (
    SpeechSubmissionRequestSerializer, 
    SpeechSubmissionResponseSerializer, 
    SpeechSubmissionStatusSerializer
)
from ..services.speaking_service import SpeakingEvaluationService


class SpeakingSubmissionViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    """
    ViewSet for submitting audio and checking status of speaking exercises.
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Enforce user ownership at the queryset level
        return SpeechSubmission.objects.filter(user=self.request.user).select_related('attempt', 'step').all()

    def get_serializer_class(self):
        if self.action == 'submit':
            return SpeechSubmissionRequestSerializer
        return SpeechSubmissionStatusSerializer

    @action(detail=False, methods=['post'])
    def submit(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            submission = SpeakingEvaluationService.create_submission(
                user=request.user,
                session_id=str(serializer.validated_data['session_id']),
                step_id=str(serializer.validated_data['step_id']),
                audio_file=serializer.validated_data['audio_file']
            )
            
            # Since we are in an environment without Celery, run evaluation synchronously
            # In production this would be: SpeakingEvaluationService.delay_processing(submission.id)
            try:
                SpeakingEvaluationService.process_evaluation(submission.id)
            except Exception as e:
                logger.error(f"Sync evaluation failed for {submission.id}: {str(e)}")
                # Even if evaluation fails here, the user can still poll the status
            
            return Response(
                SpeechSubmissionResponseSerializer(submission).data, 
                status=status.HTTP_201_CREATED
            )

        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, *args, **kwargs):
        # get_object() uses get_queryset() which already filters by user
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
