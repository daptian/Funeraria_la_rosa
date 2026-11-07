from django.shortcuts import render, get_object_or_404
from datetime import datetime
from django.utils import timezone
from django.template import loader
from django.db.models import Q
from .models import Titular, Beneficiario, Mascota, PerfilUsuario
from django.http import HttpResponse, JsonResponse
from .forms import TitularForm, BeneficiarioForm, MascotaForm, PerfilUsuarioForm, ImagenPerfilForm, CambioContrasenaForm
from django.shortcuts import redirect
from django.core.paginator import Paginator
from payment.models import Pago, Plan
from payment.views import calcular_monto_plan
from django.core.paginator import Paginator
from dateutil.relativedelta import relativedelta
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from payment.forms import PlanForm
from django.contrib import messages
from django.forms.models import model_to_dict
from historial.models import AccionHistorial
from django.urls import reverse

@login_required
def titular_list(request):

    print("peticion desde:", request)

    query = request.GET.get('q', '').strip()

    query_date_inicio = request.GET.get('fecha_inicio', '').strip()
    query_date_fin = request.GET.get('fecha_fin', '').strip()

    titulares = Titular.objects.order_by('-id')

    form = TitularForm()
    form_beneficiario = BeneficiarioForm()
    form_mascota = MascotaForm()

    if query:
        titulares = titulares.filter(
            Q(cedula__icontains=query) |
            Q(nombre__icontains=query) |
            Q(apellido__icontains=query) |
            Q(numero_contrato__icontains=query) |
            Q(beneficiarios__nombre_completo__icontains=query) |
            Q(beneficiarios__cedula__icontains=query),
        ).distinct()

    if query_date_inicio and query_date_fin:
        titulares = titulares.filter(
            fecha_ingreso__range=[query_date_inicio, query_date_fin]
        )

    elementos_por_pagina = 10
    paginator = Paginator(titulares, elementos_por_pagina)

    numero_pagina = request.GET.get('page')
    page_obj =paginator.get_page(numero_pagina)


    context = {
        'query': query,
        'page_obj': page_obj,
        'form' : form,
        'form_beneficiario' : form_beneficiario,
        'form_mascota' : form_mascota,
        'fecha_inicio': query_date_inicio,
        'fecha_fin': query_date_fin

    }
    return render(request, 'titular.html', context)

def eliminar_contrato(request, titular_id):
    titular = get_object_or_404(Titular, id=titular_id)
    titular.delete()
    return JsonResponse({'success': True, 'message': 'Contrato eliminado correctamente.'})


@login_required
def beneficiarios_list(request):
    query = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    beneficiarios = Beneficiario.objects.select_related('titular').order_by(
        'titular__apellido', 'titular__nombre', 'nombre_completo'
    )
    mascotas = Mascota.objects.select_related('titular').order_by(
        'titular__apellido', 'titular__nombre', 'nombre'
    )
    if query:
        beneficiarios = beneficiarios.filter(
            Q(nombre_completo__icontains=query)
            | Q(cedula__icontains=query)
            | Q(titular__nombre__icontains=query)
            | Q(titular__apellido__icontains=query)
            | Q(titular__cedula__icontains=query)
            | Q(titular__numero_contrato__icontains=query)
        ).distinct()
        mascotas = mascotas.filter(
            Q(nombre__icontains=query)
            | Q(especie__icontains=query)
            | Q(titular__nombre__icontains=query)
            | Q(titular__apellido__icontains=query)
            | Q(titular__cedula__icontains=query)
            | Q(titular__numero_contrato__icontains=query)
        ).distinct()

    if tipo == 'persona':
        mascotas = Mascota.objects.none()
    elif tipo == 'mascota':
        beneficiarios = Beneficiario.objects.none()

    miembros = [
        {'tipo': 'beneficiario', 'objeto': item, 'titular': item.titular}
        for item in beneficiarios
    ] + [
        {'tipo': 'mascota', 'objeto': item, 'titular': item.titular}
        for item in mascotas
    ]
    miembros.sort(key=lambda item: (
        item['titular'].apellido.casefold(),
        item['titular'].nombre.casefold(),
        item['tipo'],
        (item['objeto'].nombre_completo if item['tipo'] == 'beneficiario' else item['objeto'].nombre or '').casefold(),
    ))
    page_obj = Paginator(miembros, 15).get_page(request.GET.get('page'))
    return render(request, 'beneficiarios.html', {
        'page_obj': page_obj,
        'query': query,
        'tipo': tipo,
    })


@login_required
def eliminar_beneficiario(request, titular_id, beneficiario_id):
    if request.method != 'POST':
        return HttpResponse(status=405)

    titular = get_object_or_404(Titular, pk=titular_id)
    beneficiario = get_object_or_404(Beneficiario, pk=beneficiario_id, titular=titular)
    beneficiario.delete()
    calcular_monto_plan(titular.id)
    messages.success(request, 'El beneficiario fue eliminado y se actualizó el valor del plan.')
    return redirect('beneficiarios')


@login_required
def eliminar_mascota_beneficiario(request, titular_id, mascota_id):
    if request.method != 'POST':
        return HttpResponse(status=405)

    titular = get_object_or_404(Titular, pk=titular_id)
    mascota = get_object_or_404(Mascota, pk=mascota_id, titular=titular)
    mascota.delete()
    calcular_monto_plan(titular.id)
    messages.success(request, 'La mascota fue eliminada y se actualizó el valor del plan.')
    return redirect('beneficiarios')

@login_required
def titular_dashboard(request):
    
    # Obtén directamente los datos
    historial = AccionHistorial.objects.all()
    
    tipo = request.GET.get('tipo_accion')
    if tipo:
        historial = historial.filter(tipo_accion=tipo)
    
    historial = historial[:10]
    
    context = {
        'acciones': historial,
        'tipos': AccionHistorial.TIPOS_ACCION
    }
    
    return render(request, 'dashboard.html', context)


def crear_titular(request):
    form = TitularForm(request.POST or None)
    titulares = Titular.objects.order_by('-id')
    if request.method == 'POST' and form.is_valid():
        esta_al_dia = form.cleaned_data['esta_al_dia']
        fecha_ultimo_pago = form.cleaned_data['fecha_ultimo_pago'] if esta_al_dia else None
        nuevo_titular = form.save()
        crear_primer_pago(nuevo_titular, fecha_ultimo_pago)
        return redirect('titular_list')
    context = {
        'form' : form,
        'titulares': titulares
    }
    return render(request, 'titular.html', context)


def crear_primer_pago(titular_instacia, fecha_ultimo_pago=None):
    pago = Pago(titular=titular_instacia, monto_mensual_tarifa=24000.00, monto_total_a_pagar=24000.00, monto_cargos_unicos=0)
    fecha_base = fecha_ultimo_pago or pago.titular.fecha_ingreso
    pago.proximo_pago = fecha_base + relativedelta(months=1)
    if fecha_ultimo_pago:
        pago.fecha_ultimo_pago = timezone.make_aware(
            datetime.combine(fecha_ultimo_pago, datetime.min.time())
        )
    pago.save()
    return True

def crear_beneficiario(request):
    if request.method == 'POST':
        form_beneficiario = BeneficiarioForm(request.POST)
        
        if form_beneficiario.is_valid():
            beneficiario = form_beneficiario.save()
            calcular_monto_plan(beneficiario.titular.id)
            is_ajax = (
                request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                'application/json' in request.headers.get('Accept', '')
            )

            if is_ajax:
                return JsonResponse({'success': True})
            return redirect('titular_list')
        is_ajax = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
            'application/json' in request.headers.get('Accept', '')
        )
        if is_ajax:
            return JsonResponse({'success': False, 'errors': form_beneficiario.errors}, status=400)

        context = {'form_beneficiario': form_beneficiario}
        return render(request, 'registro_beneficiario.html', context)
    
    form_beneficiario = BeneficiarioForm()
    return render(request, 'registro_beneficiario.html', {'form_beneficiario': form_beneficiario})

def crear_mascota(request):
    if request.method == 'POST':
        form_mascota = MascotaForm(request.POST)
        print(request.POST)
        if form_mascota.is_valid():
            mascota = form_mascota.save()
            calcular_monto_plan(mascota.titular.id)
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({
                    'success': True,
                    'mascota': {
                        'id': mascota.id,
                        'nombre': mascota.nombre,
                        'especie': mascota.especie,
                        'fecha': mascota.fecha_afiliacion.strftime('%d/%m/%Y') 
                    }
                })
            
            return redirect('titular_list') # Respaldo si no es AJAX
        
        # Si el formulario es inválido y es AJAX, devolvemos los errores
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form_mascota.errors}, status=400)
            
    form_mascota = MascotaForm()
    return render(request, 'crearMascotaFormModal.html', {'form_mascota': form_mascota})


# Paginación
def obtener_titulares_paginados(request):
    titulares = list(Titular.objects.values('nombre', 'apellido', 'sexo', 'edad', 'cedula', 'estado_civil', 'ocupacion','direccion', 'fecha_ingreso'))
    titulares_por_pagina = 10
    paginator = Paginator(titulares, titulares_por_pagina)

    numero_pagina = request.GET.get('page', 1)
    pagina_actual = paginator.get_page(numero_pagina)

    return JsonResponse({
        'titulares' : pagina_actual.object_list,
        'tiene_siguiente': pagina_actual.has_next(),
        'tiene_anterior': pagina_actual.has_previous(),
        'pagina_actual': pagina_actual.number,
        'total_paginas': paginator.num_pages
    })

def obtener_miembros_paginados(request, titular_id):
    beneficiarios = list(Beneficiario.objects.filter(titular_id=titular_id).values('id', 'nombre_completo', 'cedula', 'parentesco', 'edad_afiliacion', 'fecha_afiliacion'))
    mascotas = list(Mascota.objects.filter(titular_id=titular_id).values('id', 'nombre', 'especie', 'fecha_afiliacion'))

    lista_mascotas = [
        {
            'id': m['id'],
            'nombre_completo': f"{m['nombre']} (🐾 Mascota)",
            'cedula': '-',
            'parentesco': m['especie'],
            'edad_afiliacion': '-',
            'fecha_afiliacion': m['fecha_afiliacion'],
        } for m in mascotas
    ]
    
    todos_los_miembros = beneficiarios + lista_mascotas

    elementos_por_pagina = 6
    paginator = Paginator(todos_los_miembros, elementos_por_pagina)
    
    numero_pagina = request.GET.get('page', 1)
    pagina_actual = paginator.get_page(numero_pagina)

    return JsonResponse({
        'resultados': pagina_actual.object_list,
        'tiene_siguiente': pagina_actual.has_next(),
        'tiene_anterior': pagina_actual.has_previous(),
        'pagina_actual': pagina_actual.number,
        'total_paginas': paginator.num_pages
    })

def obtener_contrato(request, titular_id):
    titular = get_object_or_404(Titular, id=titular_id)
    beneficiarios = list(Beneficiario.objects.filter(titular=titular))
    mascotas = list(Mascota.objects.filter(titular=titular))

    context = {
        'titular': model_to_dict(titular, fields=['nombre', 'apellido', 'cedula', 'numero_contrato', 'direccion', 'telefono', 'fecha_ingreso', 'plan_activo', 'edad', 'estado_civil', 'ocupacion', 'sexo' ]),
        'fecha_ingreso': titular.fecha_ingreso.strftime('%d/%m/%Y') if titular.fecha_ingreso else '',
        'beneficiarios': [model_to_dict(b) for b in beneficiarios],
        'mascotas': [model_to_dict(m) for m in mascotas],
    }

    return JsonResponse({'contenido': context})


def titular_edit(request, titular_id):
    titular = get_object_or_404(Titular, id=titular_id)

    if request.method == "POST":
        form = TitularForm(request.POST, instance=titular)
        if form.is_valid():
            form.save()
            messages.success(request, 'Se actualizó el usuario correctamente')
            return JsonResponse({
                'status': 'success', 
                'redirect_url': reverse('titular_list')
            })
        else:
            return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)

    return JsonResponse({
        'titular': model_to_dict(titular)
    })


"""
Vista de Configuración
"""
@login_required
def config_dashboard(request):
    if not Plan.objects.exists():
        Plan.objects.create(
            valor_mensual=000,
            valor_mascotas=0.00,
            valor_beneficiario_extra=0.00,
            valor_cobro_edad=0.00,
            edad_maxima=0
        )

    return render(request, "settings/conf.html", _contexto_configuracion(request))


def _contexto_configuracion(request, perfil_form=None, imagen_form=None, password_form=None):
    configuration = {
        plan.id: {
            'valor_mensual': plan.valor_mensual,
            'valor_mascotas': plan.valor_mascotas,
            'valor_beneficiario_extra': plan.valor_beneficiario_extra,
            'valor_cobro_edad': plan.valor_cobro_edad,
            'edad_maxima': plan.edad_maxima,
        } for plan in Plan.objects.all()
    }
    perfil, _ = PerfilUsuario.objects.get_or_create(usuario=request.user)
    return {
        'configuration': configuration,
        'perfil': perfil,
        'perfil_form': perfil_form or PerfilUsuarioForm(instance=request.user),
        'imagen_form': imagen_form or ImagenPerfilForm(instance=perfil),
        'password_form': password_form or CambioContrasenaForm(request.user),
    }


@login_required
def actualizar_perfil(request):
    if request.method != 'POST':
        return HttpResponse(status=405)

    perfil, _ = PerfilUsuario.objects.get_or_create(usuario=request.user)
    perfil_form = PerfilUsuarioForm(request.POST, instance=request.user)
    imagen_form = ImagenPerfilForm(request.POST, request.FILES, instance=perfil)
    if perfil_form.is_valid() and imagen_form.is_valid():
        perfil_form.save()
        imagen_form.save()
        messages.success(request, 'Tus datos de perfil se actualizaron correctamente.')
    else:
        return render(request, 'settings/conf.html', _contexto_configuracion(
            request,
            perfil_form=perfil_form,
            imagen_form=imagen_form,
        ))
    return redirect('config')


@login_required
def cambiar_contrasena(request):
    if request.method != 'POST':
        return HttpResponse(status=405)

    form = CambioContrasenaForm(request.user, request.POST)
    if form.is_valid():
        usuario = form.save()
        update_session_auth_hash(request, usuario)
        messages.success(request, 'La contraseña se cambió correctamente.')
    else:
        return render(request, 'settings/conf.html', _contexto_configuracion(
            request,
            password_form=form,
        ))
    return redirect('config')

def editar_configuracion(request, pk):
    plan = get_object_or_404(Plan, id=pk)
    if request.method == 'POST':
        form = PlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuración actualizada correctamente.')
        return redirect('config')
    else:
        form = PlanForm(instance=plan)
    return render(request, "settings/editplans.html", {'plan': plan, 'form': form })

#Vista de login
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Bienvenido, {username}!")
                return redirect('dashboard')
        else:
            messages.error(request, "Nombre de usuario o contraseña incorrectos.")
    else:
        form = AuthenticationForm()
    
    return render(request, 'login/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')
