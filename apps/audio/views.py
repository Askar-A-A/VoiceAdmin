from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from django.db.models import Sum
from django.views import View
from .models import AudioFile
from .forms import AudioUploadForm
from .services import upload_to_carrierx, delete_from_carrierx, stream_from_carrierx


def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'home.html')


@login_required
def dashboard(request):
    files = AudioFile.objects.filter(owner=request.user)
    total_bytes = files.aggregate(total=Sum('size_bytes'))['total'] or 0
    return render(request, 'audio/dashboard.html', {
        'file_count': files.count(),
        'total_bytes': total_bytes,
        'recent_files': files[:5],
    })
    

@login_required
def audio_list(request):
    files = AudioFile.objects.filter(owner=request.user)

    q = request.GET.get('q', '').strip()
    if q:
        files = files.filter(name__icontains=q)

    sort = request.GET.get('sort', '-uploaded_at')
    allowed_sorts = {'name', '-name', 'uploaded_at', '-uploaded_at'}
    if sort not in allowed_sorts:
        sort = '-uploaded_at'
    files = files.order_by(sort)

    return render(request, 'audio/list.html', {
        'files': files,
        'q': q,
        'sort': sort,
    })


@login_required
def audio_delete(request, pk):
    audio = get_object_or_404(AudioFile, pk=pk, owner=request.user)
    if request.method == 'POST':
        delete_from_carrierx(audio.file_sid)
        audio.delete()
        messages.success(request, f'"{audio.name}" deleted.')
    return redirect('audio_list')


class AudioUploadView(LoginRequiredMixin, View):
    template_name = 'audio/upload.html'
    
    def get(self, request):
        return render(request, self.template_name, {'form': AudioUploadForm()})

    def post(self, request):
        form = AudioUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})
        
        uploaded_file = request.FILES['file']
        
        filename = uploaded_file.name
        display_name = form.cleaned_data.get('name') or filename
        
        file_sid = upload_to_carrierx(uploaded_file, filename)
        if not file_sid:
            messages.error(request, 'Upload to CarrierX failed. Please try again.')
            return render(request, self.template_name, {'form': form})
        
        AudioFile.objects.create(
            owner=request.user,
            name=display_name, 
            file_sid=file_sid,
            container_sid=settings.CARRIERX_CONTAINER_SID,
            size_bytes=uploaded_file.size,
            )
        messages.success(request, f'"{display_name}" uploaded successfully.')
        return redirect('audio_list')


@login_required
def audio_stream(request, pk):
    audio = get_object_or_404(AudioFile, pk=pk, owner=request.user)
    carrierx_response = stream_from_carrierx(audio.file_sid)
    if carrierx_response.status_code != 200:
        return HttpResponse(status=404)
    content_type = carrierx_response.headers.get('Content-Type', 'audio/mpeg')
    return StreamingHttpResponse(
        carrierx_response.iter_content(chunk_size=8192),
        content_type=content_type,
    )


@login_required
def audio_detail(request, pk):
    audio = get_object_or_404(AudioFile, pk=pk, owner=request.user)
    if request.method == 'POST':
        new_name = request.POST.get('name', '').strip()     
        if new_name:
            audio.name = new_name
            audio.save(update_fields=['name'])
            messages.success(request, 'File renamed.') 
            return redirect('audio_detail', pk=audio.pk)
        messages.error(request, 'Name cannot be empty.')
    return render(request, 'audio/detail.html', {'audio': audio})


@login_required
def audio_download(request, pk):
    audio = get_object_or_404(AudioFile, pk=pk, owner=request.user)
    carrierx_response = stream_from_carrierx(audio.file_sid)
    if carrierx_response.status_code != 200:
        return HttpResponse(status=404)

    content_type = carrierx_response.headers.get('Content-Type', 'audio/mpeg')
    filename = audio.name.replace('"', '')
    if '.' not in filename:
        filename += '.mp3'

    response = StreamingHttpResponse(
        carrierx_response.iter_content(chunk_size=8192),
        content_type=content_type,
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_POST
def audio_upload_ajax(request):
    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return JsonResponse({'success': False, 'error': 'No file provided.'}, status=400)

    max_size = getattr(settings, 'MAX_AUDIO_UPLOAD_SIZE', 50 * 1024 * 1024)
    if uploaded_file.size > max_size:
        return JsonResponse(
            {'success': False, 'error': f'File too large (max {max_size // (1024 * 1024)} MB).'},
            status=400,
        )

    filename = uploaded_file.name
    file_sid = upload_to_carrierx(uploaded_file, filename)
    if not file_sid:
        return JsonResponse({'success': False, 'error': 'CarrierX upload failed.'}, status=502)
    
    AudioFile.objects.create(
        owner=request.user,
        name=filename,
        file_sid=file_sid,
        container_sid=settings.CARRIERX_CONTAINER_SID,
        size_bytes=uploaded_file.size,
    )
    return JsonResponse({'success': True, 'name': filename})
