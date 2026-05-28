import pandas as pd
import requests
import datetime
from datetime import timedelta
import numpy as np
import json
import sys
import os


def notas(rango,f,folio,auto_confirm=False):
    for i in range(rango,rango+1):
        #print(folio)
        if f['Tipo'][i]=='NC':
            t_doc='2'
            t_comp='E'
            t_rel='01'
        else:
            t_doc='3'
            t_comp='I'
            t_rel='02'
        folio=int(folio)+1
        print(folio)
        _mexico = datetime.timezone(datetime.timedelta(hours=-6))
        dia=datetime.datetime.now(_mexico).strftime("%Y-%m-%dT%H:%M:%S")
        periodo=(str(f['Periodo ECD'][i]))
        limite=str(f['Fecha Limite de Pago'][i])
        perecd=f"{periodo[8:10]}-{periodo[5:7]}-{periodo[0:4]}"
        flimite=f"{limite[:2]}-{limite[3:5]}-{limite[6:]}"
        perecd2=f"{periodo[0:4]}-{periodo[5:7]}-{periodo[8:10]}"
        flimite2=f"{limite[6:]}-{limite[3:5]}-{limite[0:2]}"
        body= u"""{
       "user": "XTS191120H32",
       "password": "portalxiix",
       "datosAdicionales": {
        "DocumentoNota": \"Periodo ECD:"""+perecd+""" Factura (FUF):"""+f['FUF'][i]+""" Fecha Limite de Pago:"""+flimite+""" ID Participante:"""+f['Participante'][i]+""" Correo:escuderop@xiix.mx Ref. Banco:"""+f['FUF'][i]+""" Sucursal:0031 Banco:BBVA Cuenta:0114254848 CLABE:012180001142548489\",
        "TipoDeComprobante": \""""+f['Tipo'][i]+"""\" ,
        "LABEL": "CABADD",
        "TIPO_DOC": \""""+t_doc+"""\",
        "CODIGO_FUF": \""""+f['FUF'][i]+"""\",
        "PERIODO_ECD": \""""+perecd2+"""\",
        "FECHA_LIM_PAGO": \""""+flimite2+"""\",
        "ID_PARTIC_CENACE": \""""+f['Participante'][i]+"""\",
        "BANCO": "BBVA",
        "SUCURSAL": "0031",
        "CUENTA": "0114254848",
        "CLABE": "012180001142548489",
        "REF_BANCO": \""""+f['FUF'][i]+"""\",
        "CONTACTO": "escuderop@xiix.mx",
        "NUM_LIN_0": "1",
        "LABEL_0": "LINADD",
        "FOLIO_UNICO_0": \""""+str(f['No. Identificacion'][i])+"""\",
        "IMPORTE_MODF_0": \""""+f"{float(f['Importe Modificado'][i]):.2f}"+"""\",
        "MONTO_AJUSTE_0": \""""+f"{float(f['Monto Ajuste'][i]):.2f}"+"""\",
        "IMPORTE_ORIG_0": \""""+f"{float(f['Importe Original'][i]):.2f}"+"""\",
        "NUM_LIN_1": "2",
        "LABEL_1": "LINADD",
        "FOLIO_UNICO_1": \""""+str(f['No. Identificacion'][i+1])+"""\",
        "IMPORTE_MODF_1": \""""+f"{float(f['Importe Modificado'][i+1]):.2f}"+"""\",
        "MONTO_AJUSTE_1": \""""+f"{float(f['Monto Ajuste'][i+1]):.2f}"+"""\",
        "IMPORTE_ORIG_1": \""""+f"{float(f['Importe Original'][i+1]):.2f}"+"""\"
      },
      "Comprobante": {
        "Exportacion": "01",
        "Serie": \""""+f['Tipo'][i]+"""\",
        "Folio": \""""+str(folio)+"""\",
        "Fecha": \""""+str(dia)+"""\",
        "SubTotal": \""""+str(round((f['Subtotal'][i])+(f['Subtotal'][i+1]),2))+"""\",
        "Moneda": "MXN",
        "Total": \""""+str(round((f['TOTAL'][i])+(f['TOTAL'][i+1]),2))+"""\",
        "TipoDeComprobante": \""""+t_comp+"""\",
        "FormaPago": "99",
        "MetodoPago": "PPD",
        "CondicionesDePago": "60 DIAS (TUA)",
        "Descuento": \""""+f"{float(f['Descuento'][i]):.2f}"+"""\",
        "TipoCambio": "1",
        "LugarExpedicion": "05348",
        "Confirmacion": "",
        "Version": "4.0",
        "InformacionGlobal": {
          "Periodicidad": "",
          "Meses": "",
          "Anio": ""
        },
        "CfdiRelacionados": [
          {
            "TipoRelacion": \""""+t_rel+"""\",
            "CfdiRelacionado": [
              {
                "UUID": \""""+f['Folio Fiscal'][i]+"""\"
              }
            ]
          }
        ],
        "Emisor": {
          "Rfc": "XTS191120H32",
          "Nombre": "XIIX TRADING SOLUTIONS",
          "RegimenFiscal": "601"
        },
        "Receptor": {
          "email": "",
          "numInt": "",
          "municipio": "ALVARO OBREGON",
          "colonia": "LOS ALPES",
          "estado": "MEXICO",
          "calle": "BOULEVARD ADOLFO LOPEZ MATEOS",
          "pais": "MEX",
          "Rfc": "CNC140828PQ4",
          "Nombre": "CENTRO NACIONAL DE CONTROL DE ENERGIA",
          "ResidenciaFiscal": "",
          "NumRegIdTrib": "",
          "UsoCFDI": "G01",
          "Pais": "MEX",
          "Estado": "MEXICO",
          "Municipio": "ALVARO OBREGON",
          "codigoPostal": "01010",
          "Colonia": "LOS ALPES",
          "NumInt": "",
          "noExterior": "2157",
          "Calle": "BOULEVARD ADOLFO LOPEZ MATEOS",
          "RegimenFiscalReceptor": "603",
          "DomicilioFiscalReceptor": "01010"
        },
        "Conceptos": {
          "Concepto": [
            {
              "ClaveProdServ": "83101800",
              "NoIdentificacion": \""""+f['No. Identificacion'][i]+"""\",
              "ClaveUnidad": \""""+f['ClaveUnidad'][i]+"""\",
              "Unidad": \""""+f['Unidad'][i]+"""\",
              "Descripcion": \""""+f['Descripcion'][i]+"""\",
              "Importe": \""""+f"{float(f['Importe'][i]):.2f}"+"""\",
              "Cantidad": \""""+str(round(f['Cantidad'][i],2))+"""\",
              "ValorUnitario": \""""+f"{float(f['Precio Unitario'][i]):.2f}"+"""\",
              "IMPORTE_ORIG": \""""+f"{float(f['Importe Original'][i]):.2f}"+"""\",
              "IMPORTE_MODF": \""""+f"{float(f['Importe Modificado'][i]):.2f}"+"""\",
              "MONTO_AJUSTE": \""""+f"{float(f['Monto Ajuste'][i]):.2f}"+"""\",
              "Descuento": \""""+f"{float(f['Descuento'][i]):.2f}"+"""\",
              "ObjetoImp": "02",
              "Impuestos": {
                "Traslados": {
                  "Traslado": [
                    {
                      "Impuesto": "002",
                      "TasaOCuota": "0.160000",
                      "Importe": \""""+f"{float(f['Importe'][i])*0.16:.2f}"+"""\",
                      "TipoFactor": "Tasa",
                      "Base": \""""+f"{float(f['Importe'][i]):.2f}"+"""\"
                    }
                  ]
                },
                "Retenciones": {
                  "Retencion": [
                    
                  ]
                }
              },
              "InformacionAduanera": null
            },
            {
               "ClaveProdServ": "83101800",
               "NoIdentificacion": \""""+f['No. Identificacion'][i+1]+"""\",
               "ClaveUnidad": \""""+f['ClaveUnidad'][i+1]+"""\",
               "Unidad": \""""+f['Unidad'][i+1]+"""\",
               "Descripcion": \""""+f['Descripcion'][i+1]+"""\",
               "Importe": \""""+f"{float(f['Importe'][i+1]):.2f}"+"""\",
               "Cantidad": \""""+str(round(f['Cantidad'][i+1],2))+"""\",
               "ValorUnitario": \""""+f"{float(f['Precio Unitario'][i+1]):.2f}"+"""\",
               "IMPORTE_ORIG": \""""+f"{float(f['Importe Original'][i+1]):.2f}"+"""\",
               "IMPORTE_MODF": \""""+f"{float(f['Importe Modificado'][i+1]):.2f}"+"""\",
               "MONTO_AJUSTE": \""""+f"{float(f['Monto Ajuste'][i+1]):.2f}"+"""\",
               "Descuento": \""""+f"{float(f['Descuento'][i+1]):.2f}"+"""\",
               "ObjetoImp": "02",
               "Impuestos": {
                 "Traslados": {
                   "Traslado": [
                     {
                       "Impuesto": "002",
                       "TasaOCuota": "0.160000",
                       "Importe": \""""+f"{float(f['Importe'][i+1])*0.16:.2f}"+"""\",
                       "TipoFactor": "Tasa",
                       "Base": \""""+f"{float(f['Importe'][i+1]):.2f}"+"""\"
                     }
                   ]
                 },
                 "Retenciones": {
                   "Retencion": [
                     
                   ]
                 }
               },
               "InformacionAduanera": null
             } 
          ]
        },
        "Impuestos": null,
        "TimbreFiscalDigital": null,
        "Complemento": null
      }
            }"""
        url='https://clickfactura.com.mx/api/timbrado/xml33/timbradorest/'
        heads={
            'Content-Type': 'application/json'
            }
        print(body)
        print('¿Es correcta la nota?')
        val = 'y' if auto_confirm else input('y/n:')
        if val=='y':
            response=requests.post(url, data=body.encode('utf-8'), headers=heads)
            print(f'[DEBUG] Status: {response.status_code}')
            print(f'[DEBUG] Response: {response.text[:1000]}')
            try:
                import base64 as _b64, xml.etree.ElementTree as _ET, os as _os, csv as _csv
                rj = response.json()
                codigo = rj.get('message', {}).get('codigo', '')
                resultado = rj.get('message', {}).get('resultado', '')
                xml_b64 = rj.get('message', {}).get('xmlData', '')
                uuid = ''
                if xml_b64:
                    xml_str = _b64.b64decode(xml_b64).decode('utf-8')
                    print(f'[XML Click Factura]\n{xml_str[:2000]}')
                    root = _ET.fromstring(xml_str)
                    tfd = root.find('.//{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital')
                    if tfd is not None:
                        uuid = tfd.get('UUID', '')
                    else:
                        for tag in root.iter():
                            if tag.text and tag.text.strip():
                                print(f'  <{tag.tag}>: {tag.text.strip()}')
                if codigo and codigo != '200' and codigo != '201':
                    print(f'✗ Click Factura error: codigo={codigo}, resultado={resultado}')
                elif uuid:
                    print(f'✓ UUID: {uuid}')
                fuf = str(f['FUF'][i])
                _base_fac = os.environ.get('FACTURACION_BASE', os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Facturacion')))
                _csv_path = os.path.join(_base_fac, 'folios_timbrados.csv')
                _exists = _os.path.exists(_csv_path)
                with open(_csv_path, 'a', newline='', encoding='utf-8') as _cf:
                    _w = _csv.writer(_cf)
                    if not _exists:
                        _w.writerow(['FUF', 'UUID'])
                    _w.writerow([fuf, uuid])
                print(f'✓ UUID guardado: {uuid}')
            except Exception as _ex:
                print(f'Advertencia: no se pudo procesar respuesta ({_ex})')
            print('OK')
        if val=='n':
            print('=================================================')
            print("        Esta nota no se subió")
            print('=================================================')
            print("")
            print("Continuar con la siguiente: 1")
            print("Detener el proceso: 2")
            print("")
            ok = '1' if auto_confirm else input("Continuar/Detener:")
            if ok=='1':
                print('=======================================')
                print("     Continuamos")
                print('=======================================')
            if ok=='2':
                print('=======================================')
                print("     Se detuvo el envío")
                print('=======================================')
                break
    return folio
