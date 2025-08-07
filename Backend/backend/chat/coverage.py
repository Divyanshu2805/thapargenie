"""What the knowledge base covers, for the student "What can I ask?" page.

Counts only: no titles or content. Cached briefly and cleared whenever the knowledge
base changes (receivers.py).
"""

from django.core.cache import cache
from django.db.models import Count, Max
from knowledge.models import Category, Document, DocumentStatus

CACHE_KEY = 'chat:coverage'
CACHE_SECONDS = 600
# Display order on the page; `other` is not a topic a student can ask about.
ORDER = [
    Category.FEES_SCHOLARSHIPS, Category.ADMISSIONS, Category.ACADEMIC_CALENDAR,
    Category.HOSTEL_CAMPUS_LIFE, Category.COURSES_SYLLABUS, Category.RULES_REGULATIONS,
    Category.NOTICES, Category.PLACEMENTS, Category.DEPARTMENTS, Category.FACULTY,
    Category.ABOUT_CONTACT, Category.FAQ,
]


def summary():
    data = cache.get(CACHE_KEY)
    if data is None:
        rows = {
            row['category']: row for row in Document.objects.filter(status=DocumentStatus.READY)
            .values('category').annotate(documents=Count('id'), updated_at=Max('processed_at'))
        }
        categories = [
            {
                'category': category.value,
                'label': category.label,
                'documents': rows[category]['documents'],
                'updated_at': (rows[category]['updated_at'].isoformat()
                               if rows[category]['updated_at'] else None),
            }
            for category in ORDER if category in rows
        ]
        data = {'total_documents': sum(row['documents'] for row in rows.values()),
                'categories': categories}
        cache.set(CACHE_KEY, data, CACHE_SECONDS)
    return data


def forget():
    cache.delete(CACHE_KEY)
