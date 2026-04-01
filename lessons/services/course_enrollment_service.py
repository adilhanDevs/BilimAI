from ..models.progress import CourseEnrollment
from ..models.course import Course


class CourseEnrollmentService:
    @staticmethod
    def is_enrolled(user, course: Course) -> bool:
        """
        Check if user is actively enrolled in the course.
        """
        if not user.is_authenticated:
            return False
            
        return CourseEnrollment.objects.filter(
            user=user, 
            course=course, 
            is_active=True
        ).exists()

    @staticmethod
    def ensure_enrollment(user, course: Course):
        """
        Creates an enrollment if it doesn't exist.
        """
        CourseEnrollment.objects.get_or_create(
            user=user, 
            course=course,
            defaults={'is_active': True}
        )
