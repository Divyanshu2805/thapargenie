from django.urls import path

from notices import views

urlpatterns = [
    path('notices/', views.NoticeListView.as_view(), name='notices'),
    path('notices/official/', views.OfficialNoticeListView.as_view(), name='notices-official'),
    path('notices/official/<uuid:document_id>/open/', views.OfficialNoticeOpenView.as_view(),
         name='notices-official-open'),
]
