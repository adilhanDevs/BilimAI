from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError
from .models.course import Lesson
from .models.engine import LessonStep
from .models.progress import LessonSession, ReviewItem, CourseEnrollment
from .serializers import (
    LessonStepSerializer, AttemptRequestSerializer, AttemptResponseSerializer,
    ReviewItemSerializer, CourseSummarySerializer, SessionStatusSerializer
)
from .services import AttemptSubmissionService, CourseEnrollmentService


class LessonStepViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving steps belonging to a lesson.
    Optimized for N+1 query safety using Registry-based QuerySet.
    Enforces course enrollment.
    """
    serializer_class = LessonStepSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        lesson_id = self.kwargs.get('lesson_pk')
        lang = self.request.query_params.get('lang', 'en')
        if not lesson_id:
            return LessonStep.objects.none()
        
        # 1. Verify lesson existence and enrollment
        try:
            lesson = Lesson.objects.select_related('category__course').get(id=lesson_id)
            if not CourseEnrollmentService.is_enrolled(self.request.user, lesson.category.course):
                return LessonStep.objects.none()
        except Lesson.DoesNotExist:
            return LessonStep.objects.none()
        
        # 2. Optimized queryset
        return LessonStep.objects.with_details(lang=lang).filter(lesson_id=lesson_id).order_by('sort_order')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['lang'] = self.request.query_params.get('lang', 'en')
        return context

    @action(detail=False, methods=['get'], url_path='progress')
    def progress(self, request, lesson_pk=None):
        from .models.progress import UserLessonProgress
        from .serializers import LessonProgressSerializer
        
        # Verify enrollment
        try:
            lesson = Lesson.objects.select_related('category__course').get(id=lesson_pk)
            if not CourseEnrollmentService.is_enrolled(request.user, lesson.category.course):
                return Response({"detail": "User is not enrolled in this course."}, status=status.HTTP_403_FORBIDDEN)
        except Lesson.DoesNotExist:
            return Response({"detail": "Lesson not found."}, status=status.HTTP_404_NOT_FOUND)

        progress, _ = UserLessonProgress.objects.get_or_create(user=request.user, lesson_id=lesson_pk)
        serializer = LessonProgressSerializer(progress)
        return Response(serializer.data)


class ReviewQueueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving and managing the user's review queue (SRS).
    """
    serializer_class = ReviewItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ReviewItem.objects.filter(
            user=self.request.user, 
            is_completed=False
        ).order_by('due_at')

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        instance = self.get_object()
        instance.is_completed = True
        instance.save()
        return Response({"status": "resolved"})


class UserProgressViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for high-level progress summaries across courses.
    """
    serializer_class = CourseSummarySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CourseEnrollment.objects.filter(
            user=self.request.user,
            is_active=True
        ).select_related('course').order_by('-started_at')
class AttemptViewSet(viewsets.GenericViewSet):
    """
    ViewSet for submitting attempts and session status.
    """
    serializer_class = AttemptRequestSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def submit(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # 1. Coordinate Submission via Service
            # We also need the session object back to include it in the response
            from .models.progress import LessonSession
            from django.db.models import Count
            
            result = AttemptSubmissionService.submit_attempt(
                user=request.user,
                session_id=str(serializer.validated_data['session_id']),
                step_id=str(serializer.validated_data['step_id']),
                payload=serializer.validated_data['payload']
            )
            
            # Re-fetch session with annotation for the snapshot
            session = LessonSession.objects.annotate(
                total_steps_count=Count('lesson__steps')
            ).get(id=serializer.validated_data['session_id'])
            
            # 2. Map service result to response
            from .serializers import AttemptResponseSerializer
            # Inject session into the result-like object for the serializer
            # SubmissionResult is a dataclass, we can add the session to it dynamically
            # or just pass it in context. Let's add it to the result object.
            setattr(result, 'session', session)
            
            response_serializer = AttemptResponseSerializer(result)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='session/(?P<session_id>[^/.]+)')
    def session_status(self, request, session_id=None):
        from .models.progress import LessonSession
        from .serializers import SessionStatusSerializer
        from django.db.models import Count
        try:
            session = LessonSession.objects.annotate(
                total_steps_count=Count('lesson__steps')
            ).select_related('lesson').get(id=session_id, user=request.user)
            serializer = SessionStatusSerializer(session)
            return Response(serializer.data)
        except LessonSession.DoesNotExist:
            return Response({"detail": "Session not found."}, status=status.HTTP_404_NOT_FOUND)
