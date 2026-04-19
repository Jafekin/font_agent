"""Views for ancient script ocr app with end-to-end RAG integration."""
import base64
import io
import json
import logging
import os
import tempfile
from datetime import datetime

from django.conf import settings
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from PIL import Image

from .models import ScriptAnalysis
from rag.agent import AgenticRAGPipeline
from rag.naive.pipeline import analyze_with_llm

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 1 * 1024 * 1024

try:  # Pillow >= 10 namespaces resampling filters
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
except AttributeError:  # pragma: no cover - fallback for older Pillow
    RESAMPLE_LANCZOS = Image.LANCZOS

_RAG_PIPELINE: AgenticRAGPipeline | None = None


def _get_rag_pipeline() -> AgenticRAGPipeline:
    """Lazy-load a shared RAG pipeline instance."""
    global _RAG_PIPELINE
    if _RAG_PIPELINE is None:
        index_path = getattr(settings, 'RAG_INDEX_PATH', None)
        if not index_path:
            index_path = os.path.join(settings.BASE_DIR, 'rag', 'naive', 'index')
        logger.info("Initializing agentic RAG pipeline with index %s", index_path)
        _RAG_PIPELINE = AgenticRAGPipeline(index_path=index_path)
    return _RAG_PIPELINE


def _compress_image_to_limit(path: str, max_bytes: int = MAX_UPLOAD_BYTES) -> None:
    """Re-encode/downscale an image until it is below ``max_bytes`` when possible."""
    if not path or not os.path.exists(path):
        return
    if os.path.getsize(path) <= max_bytes:
        return

    try:
        with Image.open(path) as img:
            img.load()
            original_format = (img.format or 'PNG').upper()
            candidates: list[tuple[str, Image.Image]] = [
                (original_format, img.copy())]
            if original_format not in {'JPEG', 'JPG', 'WEBP'}:
                candidates.append(('JPEG', img.convert('RGB')))

            for target_format, base_image in candidates:
                supports_quality = target_format in {'JPEG', 'JPG', 'WEBP'}
                quality_steps = [95, 85, 75, 65, 55, 45,
                                 35] if supports_quality else [None]
                scales = [1.0, 0.85, 0.7, 0.55, 0.4, 0.25]

                for scale in scales:
                    if scale == 1.0:
                        scaled_image = base_image
                    else:
                        new_size = (
                            max(1, int(base_image.width * scale)),
                            max(1, int(base_image.height * scale))
                        )
                        scaled_image = base_image.resize(
                            new_size, RESAMPLE_LANCZOS)

                    for quality in quality_steps:
                        buffer = io.BytesIO()
                        save_kwargs = {'optimize': True}
                        if supports_quality and quality is not None:
                            save_kwargs['quality'] = quality

                        scaled_image.save(
                            buffer, format=target_format, **save_kwargs)
                        size = buffer.tell()
                        if size <= max_bytes:
                            with open(path, 'wb') as outfile:
                                outfile.write(buffer.getvalue())
                            logger.debug(
                                "Compressed %s to %d bytes (format=%s scale=%.2f quality=%s)",
                                path,
                                size,
                                target_format,
                                scale,
                                quality,
                            )
                            return

                        is_last_quality = quality is None or quality == quality_steps[-1]
                        if is_last_quality:
                            # Persist best effort for this scale before further downscaling.
                            with open(path, 'wb') as outfile:
                                outfile.write(buffer.getvalue())
                            break
                        # Try next (lower) quality setting.
                    # Proceed to next scale if still too large.

            logger.warning("Unable to shrink %s below %d bytes",
                           path, max_bytes)
    except Exception:
        logger.exception("Image compression failed for %s", path)


def _content_file_from_path(path: str, name: str | None = None) -> ContentFile | None:
    """Read a filesystem path into a Django ContentFile for model storage."""
    if not path or not os.path.exists(path):
        return None
    with open(path, 'rb') as source:
        data = source.read()
    content = ContentFile(data)
    content.name = name or os.path.basename(path)
    return content


def _persist_uploaded_file(uploaded_file) -> str:
    """Write an uploaded file to a temporary location and rewind the stream."""
    suffix = os.path.splitext(getattr(uploaded_file, 'name', 'upload.png'))[
        1] or '.png'
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    for chunk in uploaded_file.chunks():
        temp_file.write(chunk)
    temp_file.flush()
    temp_file.close()
    _compress_image_to_limit(temp_file.name)
    uploaded_file.seek(0)
    logger.debug("Persisted uploaded file %s to temp path %s",
                 getattr(uploaded_file, 'name', 'upload'), temp_file.name)
    return temp_file.name


def _persist_bytes(image_bytes: bytes, suffix: str = '.png') -> str:
    """Write raw image bytes to a temporary file and return the path."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_file.write(image_bytes)
    temp_file.flush()
    temp_file.close()
    _compress_image_to_limit(temp_file.name)
    logger.debug("Persisted raw bytes to temp path %s", temp_file.name)
    return temp_file.name


def _cleanup_temp_file(path: str) -> None:
    """Best-effort removal of temporary files."""
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            logger.warning("Failed to remove temp file %s",
                           path, exc_info=True)


def _run_rag_pipeline(image_path: str, script_type: str, hint: str):
    pipeline = _get_rag_pipeline()
    logger.info("Running RAG pipeline for image=%s script_type=%s", image_path,
                script_type)
    return pipeline.run(image_path=image_path, script_type=script_type, hint=hint)


def _ensure_result_text(text: str | None) -> str:
    return text or "无法识别古文字内容"


def _prepare_rag_response(rag_payload: dict, image_path: str, script_type: str, hint: str):
    """Normalize pipeline response and optionally fall back to direct LLM."""
    rag_success = rag_payload.get('success', False)
    result_text = rag_payload.get('analysis') if rag_success else None
    fallback_used = False

    if not rag_success:
        logger.warning(
            "RAG pipeline failed, falling back to direct LLM: %s", rag_payload.get('error'))
        try:
            with Image.open(image_path) as fallback_image:
                result_text = analyze_with_llm(
                    fallback_image, script_type, hint)
            fallback_used = True
        except Exception:
            logger.exception("Fallback LLM call failed")

    rag_meta = {
        'success': rag_success,
        'error': rag_payload.get('error'),
        'references': rag_payload.get('retrieved_references') or [],
        'scores': rag_payload.get('retrieval_scores') or [],
        'text_info': rag_payload.get('retrieved_text_info') or [],
        'citations': rag_payload.get('citations') or [],
        'num_references': rag_payload.get('num_references', 0) if rag_success else 0,
        'pipeline_mode': rag_payload.get('pipeline_mode'),
        'fallback_used': fallback_used,
        'selected_tools': rag_payload.get('selected_tools') or [],
        'agent_summary': rag_payload.get('agent_summary'),
    }

    return _ensure_result_text(result_text), rag_meta


def _serialize_for_storage(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def index(request):
    """Render the main page."""
    return render(request, 'index.html')


@require_http_methods(["POST"])
@csrf_exempt
def analyze(request):
    """API endpoint for analyzing ancient script."""
    try:
        # Get form data
        if 'image' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': '请上传图片'
            }, status=400)

        image_file = request.FILES['image']
        script_type = request.POST.get('script_type', '甲骨文')
        hint = request.POST.get('hint', '')

        logger.info("Received form analysis request script_type=%s filename=%s",
                    script_type, getattr(image_file, 'name', 'upload'))

        temp_path = _persist_uploaded_file(image_file)
        stored_file = None
        try:
            rag_payload = _run_rag_pipeline(temp_path, script_type, hint)
            result_text, rag_meta = _prepare_rag_response(
                rag_payload, temp_path, script_type, hint)
            stored_file = _content_file_from_path(
                temp_path, getattr(image_file, 'name', 'upload'))
        finally:
            _cleanup_temp_file(temp_path)

        analysis = ScriptAnalysis.objects.create(
            image=stored_file or image_file,
            script_type=script_type,
            hint=hint,
            result=result_text,
            num_references=rag_meta['num_references'],
            rag_references=_serialize_for_storage(rag_meta['references']),
            rag_scores=_serialize_for_storage(rag_meta['scores']),
            rag_text_info=_serialize_for_storage(rag_meta['text_info'])
        )

        return JsonResponse({
            'success': True,
            'result': result_text,
            'analysis_id': analysis.id,
            'rag': rag_meta
        })
        logger.info("Analysis %s completed via form request (fallback=%s)",
                    analysis.id, rag_meta['fallback_used'])

    except Exception as e:
        logger.exception("Form analysis failed")
        return JsonResponse({
            'success': False,
            'error': f'分析失败: {str(e)}'
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def analyze_base64(request):
    """API endpoint for analyzing with base64 image."""
    try:
        data = json.loads(request.body)

        if 'image' not in data:
            return JsonResponse({
                'success': False,
                'error': '请提供图片'
            }, status=400)

        # Decode base64 image
        image_data = data['image']
        if image_data.startswith('data:image'):
            image_data = image_data.split(',')[1]

        image_bytes = base64.b64decode(image_data)
        script_type = data.get('script_type', '甲骨文')
        hint = data.get('hint', '')
        filename = data.get(
            'filename') or f"upload_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.png"

        logger.info(
            "Received base64 analysis request script_type=%s", script_type)

        temp_path = _persist_bytes(image_bytes)
        stored_file = None
        try:
            rag_payload = _run_rag_pipeline(temp_path, script_type, hint)
            result_text, rag_meta = _prepare_rag_response(
                rag_payload, temp_path, script_type, hint)
            stored_file = _content_file_from_path(temp_path, filename)
        finally:
            _cleanup_temp_file(temp_path)

        fallback_file = ContentFile(image_bytes, name=filename)

        analysis = ScriptAnalysis.objects.create(
            image=stored_file or fallback_file,
            script_type=script_type,
            hint=hint,
            result=result_text,
            num_references=rag_meta['num_references'],
            rag_references=_serialize_for_storage(rag_meta['references']),
            rag_scores=_serialize_for_storage(rag_meta['scores']),
            rag_text_info=_serialize_for_storage(rag_meta['text_info'])
        )

        return JsonResponse({
            'success': True,
            'result': result_text,
            'analysis_id': analysis.id,
            'rag': rag_meta
        })
        logger.info("Analysis %s completed via base64 request (fallback=%s)",
                    analysis.id, rag_meta['fallback_used'])

    except Exception as e:
        logger.exception("Base64 analysis failed")
        return JsonResponse({
            'success': False,
            'error': f'分析失败: {str(e)}'
        }, status=500)


def history(request):
    """Get analysis history."""
    analyses = ScriptAnalysis.objects.all()[:20]

    data = []
    for analysis in analyses:
        full_result = analysis.result or ''
        preview = f"{full_result[:200]}..." if len(
            full_result) > 200 else full_result

        try:
            image_url = request.build_absolute_uri(
                analysis.image.url) if analysis.image else ''
        except ValueError:
            image_url = analysis.image.url if analysis.image else ''

        data.append({
            'id': analysis.id,
            'script_type': analysis.script_type,
            'hint': analysis.hint,
            'result_preview': preview,
            'result_full': full_result,
            'image_url': image_url,
            'created_at': analysis.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })

    return JsonResponse({'success': True, 'data': data})
