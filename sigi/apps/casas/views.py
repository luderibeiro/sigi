# -*- coding: utf-8 -*-
import csv
from datetime import datetime
from functools import reduce

from django.contrib import messages
from sigi.apps.utils import to_ascii
from geraldo.generators import PDFGenerator

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404
from django.utils.translation import ugettext as _, ungettext
from django.views.generic import View

from sigi.apps.casas.forms import PortfolioForm, AtualizaCasaForm
from sigi.apps.casas.models import Orgao, TipoOrgao, Funcionario
from sigi.apps.casas.reports import (CasasLegislativasLabels,
                                     CasasLegislativasLabelsSemPresidente)
from sigi.apps.contatos.models import (UnidadeFederativa, Municipio,
                                       Mesorregiao, Microrregiao)
from sigi.apps.ocorrencias.models import Ocorrencia
from sigi.apps.parlamentares.reports import ParlamentaresLabels
from sigi.apps.servicos.models import TipoServico
from sigi.apps.servidores.models import Servidor
from sigi.shortcuts import render_to_pdf

class importa_casas(View):
    errors = []
    total_registros = 0

    TIPO = 'tipo'
    MUNICIPIO = 'municipio'
    UF = 'uf'
    ORGAO_ENDERECO = 'orgao_endereco'
    ORGAO_BAIRRO = 'orgao_bairro'
    ORGAO_CEP = 'orgao_cep'
    ORGAO_EMAIL = 'orgao_email'
    ORGAO_PORTAL = 'orgao_portal'
    ORGAO_TELEFONES = 'orgao_telefones'
    PRESIDENTE_NOME = 'presidente_nome'
    PRESIDENTE_DATA_NASCIMENTO = 'presidente_data_nascimento'
    PRESIDENTE_TELEFONES = 'presidente_telefones'
    PRESIDENTE_EMAILS = 'presidente_emails'
    PRESIDENTE_ENDERECO = 'presidente_endereco'
    PRESIDENTE_MUNICIPIO = 'presidente_municipio'
    PRESIDENTE_BAIRRO = 'presidente_bairro'
    PRESIDENTE_CEP = 'presidente_cep'
    PRESIDENTE_REDES_SOCIAIS = 'presidente_redes_sociais'
    SERVIDOR_NOME = 'contato_nome'
    SERVIDOR_DATA_NASCIMENTO = 'contato_data_nascimento'
    SERVIDOR_TELEFONES = 'contato_telefones'
    SERVIDOR_EMAILS = 'contato_emails'
    SERVIDOR_ENDERECO = 'contato_endereco'
    SERVIDOR_MUNICIPIO = 'contato_municipio'
    SERVIDOR_BAIRRO = 'contato_bairro'
    SERVIDOR_CEP = 'contato_cep'
    SERVIDOR_REDES_SOCIAIS = 'contato_redes_sociais'
    ERROS = 'erros_importacao'

    fieldnames = [TIPO, MUNICIPIO, UF, ORGAO_ENDERECO, ORGAO_BAIRRO, ORGAO_CEP,
                  ORGAO_EMAIL, ORGAO_PORTAL, ORGAO_TELEFONES, PRESIDENTE_NOME,
                  PRESIDENTE_DATA_NASCIMENTO, PRESIDENTE_TELEFONES,
                  PRESIDENTE_EMAILS, PRESIDENTE_ENDERECO, PRESIDENTE_MUNICIPIO,
                  PRESIDENTE_BAIRRO, PRESIDENTE_CEP, PRESIDENTE_REDES_SOCIAIS,
                  SERVIDOR_NOME, SERVIDOR_DATA_NASCIMENTO, SERVIDOR_TELEFONES,
                  SERVIDOR_EMAILS, SERVIDOR_ENDERECO, SERVIDOR_MUNICIPIO,
                  SERVIDOR_BAIRRO, SERVIDOR_CEP, SERVIDOR_REDES_SOCIAIS, ERROS,]

    ID_FIELDS = {TIPO, MUNICIPIO, UF}

    ORGAO_FIELDS = {
        ORGAO_ENDERECO: 'logradouro',
        ORGAO_BAIRRO: 'bairro',
        ORGAO_CEP: 'cep',
        ORGAO_EMAIL: 'email',
        ORGAO_PORTAL: 'pagina_web',
        ORGAO_TELEFONES: 'telefones',
    }

    PRESIDENTE_FIELDS = {
        PRESIDENTE_NOME: 'nome',
        PRESIDENTE_DATA_NASCIMENTO: 'data_nascimento',
        PRESIDENTE_TELEFONES: 'nota',
        PRESIDENTE_EMAILS: 'email',
        PRESIDENTE_ENDERECO: 'endereco',
        PRESIDENTE_MUNICIPIO: 'municipio_id',
        PRESIDENTE_BAIRRO: 'bairro',
        PRESIDENTE_CEP: 'cep',
        PRESIDENTE_REDES_SOCIAIS: 'redes_sociais',
    }

    SERVIDOR_FIELDS = {
        SERVIDOR_NOME: 'nome',
        SERVIDOR_DATA_NASCIMENTO: 'data_nascimento',
        SERVIDOR_TELEFONES: 'nota',
        SERVIDOR_EMAILS: 'email',
        SERVIDOR_ENDERECO: 'endereco',
        SERVIDOR_MUNICIPIO: 'municipio_id',
        SERVIDOR_BAIRRO: 'bairro',
        SERVIDOR_CEP: 'cep',
        SERVIDOR_REDES_SOCIAIS: 'redes_sociais',
    }

    def get(self, request):
        if not request.user.is_superuser:
            return HttpResponseForbidden()

        form = AtualizaCasaForm()
        return render(request, 'casas/importar.html', {'form': form})

    def post(self, request):
        if not request.user.is_superuser:
            return HttpResponseForbidden()

        form = AtualizaCasaForm(request.POST, request.FILES)

        if form.is_valid():
            file = form.cleaned_data['arquivo']
            reader = csv.DictReader(file)
            if not self.ID_FIELDS.issubset(reader.fieldnames):
                return render(
                    request,
                    'casas/importar.html',
                    {'form': form, 'error': _(u"O arquivo não possui algum dos "
                                              u"campos obrigatórios")}
                )

            if self.importa(reader):
                # Importação concluída com êxito
                return render(
                    request,
                    'casas/importar_result.html',
                    {'file_name': file.name, 'total': self.total_registros,
                     'com_erros': 0}
                )
            else:
                # Importado com erros
                file_name = "casas-erros-{:%Y-%m-%d-%H%M}.csv".format(
                    datetime.now())
                fields = self.fieldnames
                for f in reader.fieldnames:
                    if f not in fields:
                        fields.append(f)
                with open(settings.MEDIA_ROOT+'/temp/'+file_name, "w+") as f:
                    writer = csv.DictWriter(f, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(self.errors)
                return render(
                    request,
                    'casas/importar_result.html',
                    {'file_name': file.name, 'result_file': file_name,
                     'total': self.total_registros,
                     'com_erros': len(self.errors)}
                )

                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = (
                    'attachment; filename="somefilename.csv"')
                return response
        else:
            return render(
                request,
                'casas/importar.html',
                {'form': form, 'error': u"Erro no preenchimento do formulário."}
            )

    # Atualiza ou cria funcionário
    def funcionario_update(self, setor, fields, orgao, reg):
        field_nome = (self.PRESIDENTE_NOME if setor == 'presidente' else
                      self.SERVIDOR_NOME)

        # Se não tem nome do contato (ou presidente), então não há nada a
        # atualizar. Volta o reg inalterado.
        if field_nome not in reg:
            return reg

        funcionario = orgao.funcionario_set.filter(
            setor=setor,
            nome__iexact=reg[field_nome].strip()
        )

        if funcionario.count() == 0:
            funcionario = Funcionario(
                casa_legislativa=orgao,
                nome=reg[field_nome].strip(),
                setor=setor
            )
        else:
            funcionario = funcionario.first() #HACK: Sempre atualiza o primeiro

        for key in fields:
            field_name = fields[key]
            if key in reg:
                value = reg[key].strip()
            else:
                value = ""

            if value != "":
                if field_name == 'municipio_id':
                    if ',' in value:
                        municipio, uf = value.split(',')
                    else:
                        municipio = value
                        uf = reg[self.UF]

                    try:
                        value = Municipio.objects.get(
                            nome__iexact=municipio.strip(),
                            uf__sigla=uf.strip()).pk
                    except:
                        value = None
                        reg[self.ERROS].append(
                            "Impossivel identificar o Municipio de "
                            "residencia do {contato}".format(
                                contato="Presidente" if setor == 'presidente'
                                else "Contato")
                        )
                        continue
                if field_name == 'redes_sociais':
                    value = value.replace(" ", "\r")
                if field_name == 'data_nascimento':
                    sd = value.split('/')
                    if len(sd) < 3:
                        reg[self.ERROS].append(
                            "Data de nascimento do {contato} esta em um "
                            "formato nao reconhecido. Use DD/MM/AAAA".format(
                                contato="Presidente" if setor == 'presidente'
                                else "Contato"
                            )
                        )
                        continue
                    else:
                        value = "{ano}-{mes}-{dia}".format(
                            ano=sd[2],
                            mes=sd[1],
                            dia=sd[0]
                        )
                if value != getattr(funcionario, field_name):
                    setattr(funcionario, field_name, value)
        try:
            funcionario.save()
        except Exception as e:
            reg[self.ERROS].append(
                "Erro salvando {contato}: '{message}'".format(
                    message=e.message,
                    contato="Presidente" if setor == 'presidente'
                    else "Contato")
            )

        return reg

    def importa(self, reader):
        self.errors = []
        self.total_registros = 0

        for reg in reader:
            self.total_registros += 1
            reg[self.ERROS] = []
            nome_orgao = to_ascii(reg[self.MUNICIPIO])
            orgao = Orgao.objects.filter(
                tipo__sigla=reg[self.TIPO],
                municipio__search_text__icontains=nome_orgao,
                municipio__uf__sigla=reg[self.UF]
            )
            if orgao.count() == 0:
                reg[self.ERROS].append("Nao existe orgao com esta identificacao")
                self.errors.append(reg)
                continue
            elif orgao.count() > 1:
                reg[self.ERROS].append(("Existem {count} orgaos com esta mesma "
                                "identificacao").format(count=orgao.count()))
                self.errors.append(reg)
                continue
            else:
                orgao = orgao.get()

            # Atualiza os dados do órgão
            for key in self.ORGAO_FIELDS:
                field_name = self.ORGAO_FIELDS[key]
                if key in reg:
                    value = reg[key].strip()
                    if key == self.ORGAO_TELEFONES:
                        for numero in value.split(";"):
                            numero = numero.strip()
                            try:
                                orgao.telefones.update_or_create(numero=numero)
                            except:
                                reg[self.ERROS].append(
                                    'Telefone {numero} não foi '
                                    'atualizado'.format(numero=numero)
                                )
                    elif value != "" and value != getattr(orgao, field_name):
                        setattr(orgao, field_name, value)
                try:
                    orgao.save()
                except Exception as e:
                    reg[self.ERROS].append(
                        "Erro salvando o orgao: '{message}'".format(
                            message=e.message)
                    )

            # Atualiza o presidente
            reg = self.funcionario_update("presidente", self.PRESIDENTE_FIELDS,
                                          orgao, reg)

            # Atualiza o contato
            reg = self.funcionario_update("outros", self.SERVIDOR_FIELDS,
                                          orgao, reg)

            if len(reg[self.ERROS]) > 0:
                self.errors.append(reg)

        return len(self.errors) == 0

# @param qs: queryset
# @param o: (int) number of order field
def query_ordena(qs, o):
    from sigi.apps.casas.admin import OrgaoAdmin
    list_display = OrgaoAdmin.list_display
    order_fields = []

    for order_number in o.split('.'):
        order_number = int(order_number)
        order = ''
        if order_number != abs(order_number):
            order_number = abs(order_number)
            order = '-'
        order_fields.append(order + list_display[order_number - 1])

    qs = qs.order_by(*order_fields)
    return qs


def get_for_qs(get, qs):
    """
        Verifica atributos do GET e retorna queryset correspondente
    """
    kwargs = {}
    for k, v in get.iteritems():
        if str(k) not in ('page', 'pop', 'q', '_popup', 'o', 'ot'):
            kwargs[str(k)] = v

    if 'convenio' in kwargs:
        if kwargs['convenio'] == 'SC':
            qs = qs.filter(convenio=None)
        elif kwargs['convenio'] == 'CC':
            qs = qs.exclude(convenio=None)
        else:
            qs = qs.filter(convenio__projeto_id=kwargs['convenio'])

        qs = qs.distinct('municipio__uf__nome', 'nome')
        del(kwargs['convenio'])

    if 'servico' in kwargs:
        if kwargs['servico'] == 'SS':
            qs = qs.filter(servico=None)
        elif kwargs['servico'] == 'CS':
            qs = qs.exclude(servico=None).filter(
                servico__data_desativacao__isnull=True)
        elif kwargs['servico'] == 'CR':
            qs = qs.exclude(servico__tipo_servico__modo='H') \
                                .exclude(servico=None)
        elif kwargs['servico'] == 'CH':
            qs = qs.filter(
                servico__tipo_servico__modo='H',
                servico__data_desativacao__isnull=True
            )
        else:
            qs = qs.filter(servico__tipo_servico_id=kwargs['servico'])

        qs = qs.distinct('municipio__uf__nome', 'nome')

        del(kwargs['servico'])

    qs = qs.filter(**kwargs)
    if 'o' in get:
        qs = query_ordena(qs, get['o'])

    return qs


def carrinhoOrGet_for_qs(request):
    """
       Verifica se existe casas na sessão se não verifica get e retorna qs correspondente.
    """
    if 'carrinho_casas' in request.session:
        ids = request.session['carrinho_casas']
        qs = Orgao.objects.filter(pk__in=ids)
    else:
        qs = Orgao.objects.all()
        if request.GET:
            qs = get_for_qs(request.GET, qs)
    return qs


def adicionar_casas_carrinho(request, queryset=None, id=None):
    if request.method == 'POST':
        ids_selecionados = request.POST.getlist('_selected_action')
        if 'carrinho_casas' not in request.session:
            request.session['carrinho_casas'] = ids_selecionados
        else:
            lista = request.session['carrinho_casas']
            # Verifica se id já não está adicionado
            for id in ids_selecionados:
                if id not in lista:
                    lista.append(id)
            request.session['carrinho_casas'] = lista


@login_required
def visualizar_carrinho(request):

    qs = carrinhoOrGet_for_qs(request)

    paginator = Paginator(qs, 100)

    # Make sure page request is an int. If not, deliver first page.
    # Esteja certo de que o `page request` é um inteiro. Se não, mostre a primeira página.
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    # Se o page request (9999) está fora da lista, mostre a última página.
    try:
        paginas = paginator.page(page)
    except (EmptyPage, InvalidPage):
        paginas = paginator.page(paginator.num_pages)

    carrinhoIsEmpty = not('carrinho_casas' in request.session)

    return render(
        request,
        'casas/carrinho.html',
        {
            'carIsEmpty': carrinhoIsEmpty,
            'paginas': paginas,
            'query_str': '?' + request.META['QUERY_STRING']
        }
    )


@login_required
def excluir_carrinho(request):
    if 'carrinho_casas' in request.session:
        del request.session['carrinho_casas']
        messages.info(request, u'O carrinho foi esvaziado')
    return HttpResponseRedirect('../../')


@login_required
def deleta_itens_carrinho(request):
    if request.method == 'POST':
        ids_selecionados = request.POST.getlist('_selected_action')
        if 'carrinho_casas' in request.session:
            lista = request.session['carrinho_casas']
            for item in ids_selecionados:
                lista.remove(item)
            if lista:
                request.session['carrinho_casas'] = lista
            else:
                del lista
                del request.session['carrinho_casas']

    return HttpResponseRedirect('.')


@login_required
def labels_report(request, id=None, tipo=None, formato='3x9_etiqueta'):
    """ TODO: adicionar suporte para resultado de pesquisa do admin.
    """

    if request.POST:
        if 'tipo_etiqueta' in request.POST:
            tipo = request.POST['tipo_etiqueta']
        if 'tamanho_etiqueta' in request.POST:
            formato = request.POST['tamanho_etiqueta']

    if tipo == 'sem_presidente':
        return labels_report_sem_presidente(request, id, formato)

    if id:
        qs = Orgao.objects.filter(pk=id)
    else:
        qs = carrinhoOrGet_for_qs(request)

    if not qs:
        return HttpResponseRedirect('../')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=casas.pdf'
    report = CasasLegislativasLabels(queryset=qs, formato=formato)
    report.generate_by(PDFGenerator, filename=response)

    return response


@login_required
def labels_report_parlamentar(request, id=None, formato='3x9_etiqueta'):
    """ TODO: adicionar suporte para resultado de pesquisa do admin.
    """

    if request.POST:
        if 'tamanho_etiqueta' in request.POST:
            formato = request.POST['tamanho_etiqueta']

    if id:
        legislaturas = [c.legislatura_set.latest('data_inicio') for c in Orgao.objects.filter(pk__in=id, legislatura__id__isnull=False).distinct()]
        mandatos = reduce(lambda x, y: x | y, [l.mandato_set.all() for l in legislaturas])
        parlamentares = [m.parlamentar for m in mandatos]
        qs = parlamentares

    else:
        qs = carrinhoOrGet_for_parlamentar_qs(request)

    if not qs:
        return HttpResponseRedirect('../')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=casas.pdf'
    report = ParlamentaresLabels(queryset=qs, formato=formato)
    report.generate_by(PDFGenerator, filename=response)

    return response


def carrinhoOrGet_for_parlamentar_qs(request):
    """
       Verifica se existe parlamentares na sessão se não verifica get e retorna qs correspondente.
    """
    if 'carrinho_casas' in request.session:
        ids = request.session['carrinho_casas']
        legislaturas = [c.legislatura_set.latest('data_inicio') for c in Orgao.objects.filter(pk__in=ids, legislatura__id__isnull=False).distinct()]
        mandatos = reduce(lambda x, y: x | y, [l.mandato_set.all() for l in legislaturas])
        parlamentares = [m.parlamentar for m in mandatos]
        qs = parlamentares
    else:
        legislaturas = [c.legislatura_set.latest('data_inicio') for c in Orgao.objects.all().distinct()]
        mandatos = reduce(lambda x, y: x | y, [l.mandato_set.all() for l in legislaturas])
        parlamentares = [m.parlamentar for m in mandatos]
        qs = parlamentares
        if request.GET:
            qs = get_for_qs(request.GET, qs)
    return qs


@login_required
def labels_report_sem_presidente(request, id=None, formato='2x5_etiqueta'):
    """ TODO: adicionar suporte para resultado de pesquisa do admin.
    """

    if id:
        qs = Orgao.objects.filter(pk=id)
    else:
        qs = carrinhoOrGet_for_qs(request)

    if not qs:
        return HttpResponseRedirect('../')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=casas.pdf'
    report = CasasLegislativasLabelsSemPresidente(queryset=qs, formato=formato)
    report.generate_by(PDFGenerator, filename=response)

    return response


@login_required
def report(request, id=None, tipo=None):

    if request.POST:
        if 'tipo_relatorio' in request.POST:
            tipo = request.POST['tipo_relatorio']

    if tipo == 'completo':
        return report_complete(request, id)

    if id:
        qs = Orgao.objects.filter(pk=id)
    else:
        qs = carrinhoOrGet_for_qs(request)

    if not qs:
        return HttpResponseRedirect('../')

    qs = qs.order_by('municipio__uf', 'nome')
    context = {'casas': qs, 'title': _(u"Relação de Casas Legislativas")}

    return render_to_pdf('casas/report_pdf.html', context)


@login_required
def report_complete(request, id=None):

    if id:
        qs = Orgao.objects.filter(pk=id)
    else:
        qs = carrinhoOrGet_for_qs(request)

    if not qs:
        return HttpResponseRedirect('../')

    return render_to_pdf('casas/report_complete_pdf.html', {'casas': qs})


@login_required
def casas_sem_convenio_report(request):
    qs = Orgao.objects.filter(convenio=None).order_by('municipio__uf', 'nome')

    if request.GET:
        qs = get_for_qs(request.GET, qs)
    if not qs:
        return HttpResponseRedirect('../')

    qs = qs.order_by('municipio__uf', 'nome')
    context = {'casas': qs, 'title': _(u"Casas sem convênio")}

    return render_to_pdf('casas/report_pdf.html', context)


@login_required
def export_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=casas.csv'

    writer = csv.writer(response)

    casas = carrinhoOrGet_for_qs(request)
    if not casas or not request.POST:
        return HttpResponseRedirect('../')

    atributos = request.POST.getlist("itens_csv_selected")

    try:
        atributos.insert(atributos.index(_(u'Município')), _(u'UF'))
    except ValueError:
        pass

    atributos2 = [s.encode("utf-8") for s in atributos]

    writer.writerow(atributos2)

    for casa in casas:
        lista = []
        contatos = casa.funcionario_set.exclude(nome="")
        for atributo in atributos:
            if _(u"CNPJ") == atributo:
                lista.append(casa.cnpj.encode("utf-8"))
            elif _(u"Código IBGE") == atributo:
                lista.append(str(casa.municipio.codigo_ibge).encode("utf-8"))
            elif _(u"Código TSE") == atributo:
                lista.append(str(casa.municipio.codigo_tse).encode("utf-8"))
            elif _(u"Nome") == atributo:
                lista.append(casa.nome.encode("utf-8"))
            elif _(u"Município") == atributo:
                lista.append(unicode(casa.municipio.uf.sigla).encode("utf-8"))
                lista.append(unicode(casa.municipio.nome).encode("utf-8"))
            elif _(u"Presidente") == atributo:
                # TODO: Esse encode deu erro em 25/04/2012. Comentei para que o usuário pudesse continuar seu trabalho
                # É preciso descobrir o porque do erro e fazer a correção definitiva.
                #                lista.append(str(casa.presidente or "").encode("utf-8"))
                lista.append(str(casa.presidente or ""))
            elif _(u"Logradouro") == atributo:
                lista.append(casa.logradouro.encode("utf-8"))
            elif _(u"Bairro") == atributo:
                lista.append(casa.bairro.encode("utf-8"))
            elif _(u"CEP") == atributo:
                lista.append(casa.cep.encode("utf-8"))
            elif _(u"Telefone") == atributo:
                lista.append(str(casa.telefone or ""))
            elif _(u"Página web") == atributo:
                lista.append(casa.pagina_web.encode("utf-8"))
            elif _(u"Email") == atributo:
                lista.append(casa.email.encode("utf-8"))
            elif _(u"Número de parlamentares") == atributo:
                lista.append(casa.total_parlamentares)
            elif _(u"Última alteração de endereco") == atributo:
                lista.append(casa.ult_alt_endereco)
            elif _(u"Servicos SEIT") == atributo:
                lista.append(", ".join([s.tipo_servico.nome.encode('utf-8')
                                        for s in casa.servico_set.filter(
                                            data_desativacao__isnull=True)])
                )
            elif _(u"Nome contato") == atributo:
                if contatos:
                    nomes = u", ".join([c.nome for c in contatos])
                    lista.append(nomes.encode("utf-8"))
                else:
                    lista.append('')
            elif _(u"Cargo contato") == atributo:
                if contatos:
                    cargos = u", ".join([c.cargo if c.cargo else u"?"
                                         for c in contatos])
                    lista.append(cargos.encode("utf-8"))
                else:
                    lista.append('')
            elif _(u"Email contato") == atributo:
                if contatos:
                    emails = u", ".join([c.email if c.email else u"?"
                                         for c in contatos])
                    lista.append(emails.encode("utf-8"))
                else:
                    lista.append('')
            else:
                pass

        writer.writerow(lista)

    return response


@login_required
def portfolio(request):
    page = request.GET.get('page', 1)
    tipo = request.GET.get('tipo', None)
    regiao = request.GET.get('regiao', None)
    uf_id = request.GET.get('uf', None)
    meso_id = request.GET.get('meso', None)
    micro_id = request.GET.get('micro', None)

    data = {}
    data['errors'] = []
    data['messages'] = []
    data['regioes'] = UnidadeFederativa.REGIAO_CHOICES
    data['tipos_casas'] = TipoOrgao.objects.all()
    casas = None
    gerente = None

    if tipo:
        data['tipo'] = tipo

    if micro_id:
        microrregiao = get_object_or_404(Microrregiao, pk=micro_id)
        mesorregiao = microrregiao.mesorregiao
        uf = mesorregiao.uf
        data['regiao'] = uf.regiao
        data['uf_id'] = uf.pk
        data['meso_id'] = mesorregiao.pk
        data['micro_id'] = microrregiao.pk
        data['ufs'] = UnidadeFederativa.objects.filter(regiao=uf.regiao)
        data['mesorregioes'] = uf.mesorregiao_set.all()
        data['microrregioes'] = mesorregiao.microrregiao_set.all()
        data['form'] = PortfolioForm(
            _(u'Atribuir casas da microrregiao {name} para').format(
                name=unicode(microrregiao))
        )
        data['querystring'] = 'micro={0}'.format(microrregiao.pk)
        casas = Orgao.objects.filter(
            municipio__microrregiao=microrregiao
        )
    elif meso_id:
        mesorregiao = get_object_or_404(Mesorregiao, pk=meso_id)
        uf = mesorregiao.uf
        data['regiao'] = uf.regiao
        data['uf_id'] = uf.pk
        data['meso_id'] = mesorregiao.pk
        data['ufs'] = UnidadeFederativa.objects.filter(regiao=uf.regiao)
        data['mesorregioes'] = uf.mesorregiao_set.all()
        data['microrregioes'] = mesorregiao.microrregiao_set.all()
        data['form'] = PortfolioForm(
            _(u'Atribuir casas da mesorregiao {name} para').format(
                name=unicode(mesorregiao)))
        data['querystring'] = 'meso={0}'.format(mesorregiao.pk)
        casas = Orgao.objects.filter(
            municipio__microrregiao__mesorregiao=mesorregiao
        )
    elif uf_id:
        uf = get_object_or_404(UnidadeFederativa, pk=uf_id)
        data['regiao'] = uf.regiao
        data['uf_id'] = uf.pk
        data['ufs'] = UnidadeFederativa.objects.filter(regiao=uf.regiao)
        data['mesorregioes'] = uf.mesorregiao_set.all()
        data['form'] = PortfolioForm(
            _(u'Atribuir casas do estado {name} para').format(
                name=unicode(uf)))
        data['querystring'] = 'uf={0}'.format(uf.pk)
        casas = Orgao.objects.filter(municipio__uf=uf)
    elif regiao:
        data['regiao'] = regiao
        data['ufs'] = UnidadeFederativa.objects.filter(regiao=regiao)
        data['form'] = PortfolioForm(
            _(u'Atribuir casas da região {name} para').format(
                name=[x[1] for x in UnidadeFederativa.REGIAO_CHOICES if
                 x[0] == regiao][0]))
        data['querystring'] = 'regiao={0}'.format(regiao)
        casas = Orgao.objects.filter(municipio__uf__regiao=regiao)

    if casas:
        casas = casas.order_by('municipio__uf',
                               'municipio__microrregiao__mesorregiao',
                               'municipio__microrregiao', 'municipio')

        casas.prefetch_related('municipio', 'municipio__uf',
                               'municipio__microrregiao',
                               'municipio__microrregiao__mesorregiao',
                               'gerentes_interlegis')

        if tipo:
            casas = casas.filter(tipo__sigla=tipo)
            data['querystring'] += "&tipo={0}".format(tipo)

        if request.method == 'POST':
            form = PortfolioForm(data=request.POST)
            if form.is_valid():
                gerente = form.cleaned_data['gerente']
                acao = form.cleaned_data['acao']

                count = casas.count()

                if acao == 'ADD':
                    gerente.casas_que_gerencia.add(*casas)
                    data['messages'].append(ungettext(
                        u"{count} casa adicionada para {gerente}",
                        u"{count} casas adicionadas para {gerente}",
                        count).format(count=count,gerente=gerente.nome_completo)
                    )
                elif acao == 'DEL':
                    gerente.casas_que_gerencia.remove(*casas)
                    data['messages'].append(ungettext(
                        u"{count} casa removida de {gerente}",
                        u"{count} casas removidas de {gerente}",
                        count).format(count=count,gerente=gerente.nome_completo)
                    )
                else:
                    data['errors'].append(_(u"Ação não definida"))
            else:
                data['errors'].append(_(u"Dados inválidos"))

        paginator = Paginator(casas, 30)
        try:
            pagina = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pagina = paginator.page(paginator.num_pages)
        data['page_obj'] = pagina

    return render(request, 'casas/portfolio.html', data)


def resumo_carteira(casas):
    regioes = {r[0]: 0 for r in UnidadeFederativa.REGIAO_CHOICES}
    regioes['total'] = 0
    total = regioes.copy()
    sem_produto = regioes.copy()
    tipos_servico = TipoServico.objects.all()
    dados = {ts.id: regioes.copy() for ts in tipos_servico}

    for r in casas.values('municipio__uf__regiao').annotate(quantidade=Count('id')).order_by():
        regiao = r['municipio__uf__regiao']
        quantidade = r['quantidade']
        total[regiao] = quantidade
        total['total'] += quantidade

    for r in casas.values('municipio__uf__regiao', 'servico__tipo_servico__id').annotate(quantidade=Count('id')).order_by():
        regiao = r['municipio__uf__regiao']
        servico = r['servico__tipo_servico__id']
        quantidade = r['quantidade']
        if servico is None:
            sem_produto[regiao] = quantidade
            sem_produto['total'] += quantidade
        else:
            dados[servico][regiao] = quantidade
            dados[servico]['total'] += quantidade

    dados_ocorrencia = {
        'registradas': regioes.copy(),
        'pendentes': regioes.copy(),
        'sem': regioes.copy(),
        'media': regioes.copy(),
    }

    for r in casas.values('ocorrencia__status', 'municipio__uf__regiao').annotate(quantidade=Count('id')).order_by():
        status = r['ocorrencia__status']
        regiao = r['municipio__uf__regiao']
        quantidade = r['quantidade']
        if status is None:
            dados_ocorrencia['sem'][regiao] += quantidade
            dados_ocorrencia['sem']['total'] += quantidade
        else:
            dados_ocorrencia['registradas'][regiao] += quantidade
            dados_ocorrencia['registradas']['total'] += quantidade
            if status in [Ocorrencia.STATUS_ABERTO, Ocorrencia.STATUS_REABERTO]:
                dados_ocorrencia['pendentes'][regiao] += quantidade
                dados_ocorrencia['pendentes']['total'] += quantidade

    for r in regioes:
        if (total[r] - dados_ocorrencia['sem'][r]) == 0:
            dados_ocorrencia['media'][r] = 0
        else:
            dados_ocorrencia['media'][r] = (1.0 * dados_ocorrencia['registradas'][r] / (total[r] - dados_ocorrencia['sem'][r]))

    resumo = [[_(u"Item"), _(u"Total nacional")] + [r[1] for r in UnidadeFederativa.REGIAO_CHOICES]]
    resumo.append([_(u"Casas em sua carteira"), total['total']] + [total[r[0]] for r in UnidadeFederativa.REGIAO_CHOICES])
    resumo.append({'subtitle': _(u"Uso dos produtos Interlegis")})
    resumo.append([_(u"Casas sem nenhum produto"), sem_produto['total']] + [sem_produto[r[0]] for r in UnidadeFederativa.REGIAO_CHOICES])
    resumo.extend([[ts.nome, dados[ts.id]['total']] + [dados[ts.id][r[0]] for r in UnidadeFederativa.REGIAO_CHOICES] for ts in tipos_servico])
    resumo.append({'subtitle': _(u"Registros no sistema de ocorrências")})
    resumo.append([_(u"Casas que nunca registraram ocorrências"), dados_ocorrencia['sem']['total']] + [dados_ocorrencia['sem'][r[0]] for r in UnidadeFederativa.REGIAO_CHOICES])
    resumo.append([_(u"Total de ocorrências registradas"), dados_ocorrencia['registradas']['total']] + [dados_ocorrencia['registradas'][r[0]] for r in UnidadeFederativa.REGIAO_CHOICES])
    resumo.append([_(u"Total de ocorrências pendentes"), dados_ocorrencia['pendentes']['total']] + [dados_ocorrencia['pendentes'][r[0]] for r in UnidadeFederativa.REGIAO_CHOICES])
    resumo.append([_(u"Média de ocorrências por casa"), round(dados_ocorrencia['media']['total'], 2)] + [round(dados_ocorrencia['media'][r[0]], 2) for r in UnidadeFederativa.REGIAO_CHOICES])

    return resumo


def casas_carteira(request, casas, context):
    servicos = request.GET.getlist('servico')
    sigla_regiao = request.GET.get('r', None)
    sigla_uf = request.GET.get('uf', None)
    meso_id = request.GET.get('meso', None)
    micro_id = request.GET.get('micro', None)
    servicos = request.GET.getlist('servico')
    tipos_servico = context['servicos']

    context['qs_regiao'] = ''

    if micro_id is not None:
        context['micro'] = get_object_or_404(Microrregiao, pk=micro_id)
        context['qs_regiao'] = 'micro=%s' % micro_id
        context['meso'] = context['micro'].mesorregiao
        context['uf'] = context['meso'].uf
        context['regiao'] = context['uf'].regiao
        casas = casas.filter(municipio__microrregiao=context['micro'])
    elif meso_id is not None:
        context['meso'] = get_object_or_404(Mesorregiao, pk=meso_id)
        context['qs_regiao'] = 'meso=%s' % meso_id
        context['uf'] = context['meso'].uf
        context['regiao'] = context['uf'].regiao
        casas = casas.filter(municipio__microrregiao__mesorregiao=context['meso'])
    elif sigla_uf is not None:
        context['uf'] = get_object_or_404(UnidadeFederativa, sigla=sigla_uf)
        context['qs_regiao'] = 'uf=%s' % sigla_uf
        context['regiao'] = context['uf'].regiao
        casas = casas.filter(municipio__uf=context['uf'])
    elif sigla_regiao is not None:
        context['regiao'] = sigla_regiao
        context['qs_regiao'] = 'r=%s' % sigla_regiao
        casas = casas.filter(municipio__uf__regiao=sigla_regiao)

    if 'regiao' in context:
        context['ufs'] = UnidadeFederativa.objects.filter(regiao=context['regiao'])

    todos_servicos = ['_none_'] + [s.sigla for s in tipos_servico]

    if not servicos or set(servicos) == set(todos_servicos):
        servicos = todos_servicos
        context['qs_servico'] = ''
    else:
        if '_none_' in servicos:
            casas = casas.filter(Q(servico=None) | Q(servico__tipo_servico__sigla__in=servicos))
        else:
            casas = casas.filter(servico__tipo_servico__sigla__in=servicos)
        casas = casas.distinct('nome', 'municipio__uf')
        context['qs_servico'] = "&".join(['servico=%s' % s for s in servicos])

    context['servicos_check'] = servicos

    casas = casas.select_related('municipio', 'municipio__uf', 'municipio__microrregiao', 'municipio__microrregiao__mesorregiao').prefetch_related('servico_set')

    return casas, context


@login_required
def painel_relacionamento(request):
    page = request.GET.get('page', 1)
    snippet = request.GET.get('snippet', '')
    seletor = request.GET.get('s', None)
    servidor = request.GET.get('servidor', None)
    fmt = request.GET.get('f', 'html')

    if servidor is None:
        gerente = request.user.servidor
    elif servidor == '_all':
        gerente = None
    else:
        gerente = get_object_or_404(Servidor, pk=servidor)

    if gerente is not None:
        casas = gerente.casas_que_gerencia.all()

    if gerente is None or not casas.exists():
        casas = Orgao.objects.exclude(gerentes_interlegis=None)
        gerente = None

    tipos_servico = TipoServico.objects.all()
    regioes = UnidadeFederativa.REGIAO_CHOICES

    context = {
        'seletor': seletor,
        'snippet': snippet,
        'regioes': regioes,
        'servicos': tipos_servico,
        'gerentes': Servidor.objects.exclude(casas_que_gerencia=None),
        'gerente': gerente,
        'qs_servidor': ('servidor=%s' % gerente.pk) if gerente else '',
    }

    if snippet != 'lista':
        context['resumo'] = resumo_carteira(casas)

    if snippet != 'resumo':
        casas, context = casas_carteira(request, casas, context)
        paginator = Paginator(casas, 30)
        try:
            pagina = paginator.page(page)
        except (EmptyPage, InvalidPage):
            pagina = paginator.page(paginator.num_pages)
        context['page_obj'] = pagina

    if snippet == 'lista':
        if fmt == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=casas.csv'
            writer = csv.writer(response)
            writer.writerow([
                _(u"Casa legislativa").encode('utf8'),
                _(u"Região").encode('utf8'),
                _(u"Estado").encode('utf8'),
                _(u"Mesorregião").encode('utf8'),
                _(u"Microrregião").encode('utf8'),
                _(u"Gerentes Interlegis").encode('utf8'),
                _(u"Serviços").encode('utf8'),
            ])
            for c in casas:
                writer.writerow([
                    c.nome.encode('utf8'),
                    c.municipio.uf.get_regiao_display().encode('utf8'),
                    c.municipio.uf.sigla.encode('utf8'),
                    c.municipio.microrregiao.mesorregiao.nome.encode('utf8'),
                    c.municipio.microrregiao.nome.encode('utf8'),
                    c.lista_gerentes(fmt='lista').encode('utf8'),
                    (u", ".join([s.tipo_servico.nome for s in c.servico_set.filter(data_desativacao__isnull=True)])).encode('utf8'),
                ])
            return response
        return render(request, 'casas/lista_casas_carteira_snippet.html', context)
    if snippet == 'resumo':
        return render(request, 'casas/resumo_carteira_snippet.html', context)

    return render(request, 'casas/painel.html', context)

@login_required
def gerentes_interlegis(request):
    formato = request.GET.get('fmt', 'html')
    inclui_casas = (request.GET.get('casas', 'no') == 'yes')
    gerentes = Servidor.objects.exclude(
        casas_que_gerencia=None).select_related('casas_que_gerencia')
    dados = []
    for gerente in gerentes:
        row = {'gerente': gerente, 'ufs': []}
        for uf in (gerente.casas_que_gerencia.distinct('municipio__uf__sigla')
                    .order_by('municipio__uf__sigla')
                    .values_list('municipio__uf__sigla', 'municipio__uf__nome')
                    ):
            row['ufs'].append((
                uf[0],
                uf[1],
                gerente.casas_que_gerencia.filter(municipio__uf__sigla=uf[0])
            ))
        dados.append(row)

    if formato == 'pdf':
        return render_to_pdf(
            'casas/gerentes_interlegis_pdf.html',
            {'gerentes': dados}
        )
    elif formato == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = ('attachment; '
                                           'filename="gerentes_interlegis.csv"')
        fieldnames = ['gerente', 'total_casas', 'uf', 'total_casas_uf']
        if inclui_casas:
            fieldnames.append('casa_legislativa')
        writer = csv.DictWriter(response, fieldnames=fieldnames)
        writer.writeheader()
        for linha in dados:
            rec = {
                'gerente': linha['gerente'].nome_completo.encode('utf8'),
                'total_casas': linha['gerente'].casas_que_gerencia.count()
            }
            for uf in linha['ufs']:
                rec['uf'] = uf[1].encode('utf8')
                rec['total_casas_uf'] = uf[2].count()
                if inclui_casas:
                    for casa in uf[2]:
                        rec['casa_legislativa'] = casa.nome.encode('utf8')
                        writer.writerow(rec)
                        rec['gerente'] = ''
                        rec['total_casas'] = ''
                        rec['uf'] = ''
                        rec['total_casas_uf'] = ''
                else:
                    writer.writerow(rec)
                    rec['gerente'] = ''
                    rec['total_casas'] = ''
        return response

    return render(
        request,
        'casas/gerentes_interlegis.html',
        {'gerentes': dados}
    )
