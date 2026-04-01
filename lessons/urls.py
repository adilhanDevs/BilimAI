from django.urls import path, include
from rest_framework_nested import routers
from .views import LessonStepViewSet, AttemptViewSet, ReviewQueueViewSet, UserProgressViewSet, CourseViewSet
from .api.speaking_views import SpeakingSubmissionViewSet

# We use nested routers for /lessons/<lesson_id>/steps/
router = routers.SimpleRouter()
router.register(r'courses', CourseViewSet, basename='courses')
router.register(r'attempts', AttemptViewSet, basename='attempts')
router.register(r'speaking/submissions', SpeakingSubmissionViewSet, basename='speaking-submissions')
router.register(r'reviews', ReviewQueueViewSet, basename='review-queue')
router.register(r'progress', UserProgressViewSet, basename='user-progress')


# Dummy lessons registration if not already handled in main urls.py or elsewhere
# For the sake of this implementation, we assume 'lessons' is a valid route
lessons_router = routers.SimpleRouter()
lessons_router.register(r'lessons', LessonStepViewSet, basename='lesson-steps')

steps_router = routers.NestedSimpleRouter(lessons_router, r'lessons', lookup='lesson')
steps_router.register(r'steps', LessonStepViewSet, basename='lesson-steps')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(lessons_router.urls)),
    path('', include(steps_router.urls)),
]
