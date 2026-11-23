"""REST API for waste classification (Django REST Framework)."""
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .classifier import DEMO_NOTICE, ClassifierUnavailable, InvalidImage
from .forms import ClassifyForm
from .services import classify_and_store


class ClassifyAPIView(APIView):
    """POST an `image` file; get the classification back as JSON."""

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        form = ClassifyForm(request.data, request.FILES)
        if not form.is_valid():
            return Response({"errors": form.errors}, status=status.HTTP_400_BAD_REQUEST)
        try:
            record = classify_and_store(request.user, form.cleaned_data["image"])
        except InvalidImage as error:
            return Response({"errors": {"image": [str(error)]}}, status=status.HTTP_400_BAD_REQUEST)
        except ClassifierUnavailable as error:
            return Response({"detail": str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(
            {
                "id": record.pk,
                "label": record.predicted_label,
                "label_display": record.label_display,
                "confidence": record.confidence,
                "is_demo": record.is_demo,
                "model_name": record.model_name,
                "notice": DEMO_NOTICE if record.is_demo else "",
            }
        )