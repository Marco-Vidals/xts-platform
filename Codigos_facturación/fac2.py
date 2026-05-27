import pandas as pd
import requests
import datetime
from datetime import timedelta
import numpy as np
import json
import sys
import os



def factura(rango,f,folio):
    for i in range(rango,rango+1):#len(f)):
        #print(folio)
        folio=int(folio)+1
        print(folio)
        dia=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        perecd=f"{f['Periodo ECD'][i][8:]}-{f['Periodo ECD'][i][5:7]}-{f['Periodo ECD'][i][0:4]}"
        flimite=f"{f['Fecha Limite de Pago'][i][8:]}-{f['Fecha Limite de Pago'][i][5:7]}-{f['Fecha Limite de Pago'][i][0:4]}"
        perecd2=f"{f['Periodo ECD'][i][:4]}-{f['Periodo ECD'][i][5:7]}-{f['Periodo ECD'][i][8:]}"
        flimite2=f"{f['Fecha Limite de Pago'][i][:4]}-{f['Fecha Limite de Pago'][i][5:7]}-{f['Fecha Limite de Pago'][i][8:]}"
        body=u"""{
          "user": "XTS191120H32",
          "password": "portalxiix",
          "datosAdicionales": {
            "DocumentoNota": "Periodo ECD:"""+perecd+""" Factura (FUF):"""+f['FUF'][i]+""" Fecha Limite de Pago:"""+flimite+""" ID Participante:"""+f['Participante'][i]+""" Correo:escuderop@xiix.mx Ref. Banco:"""+f['FUF'][i]+""" Sucursal:0031 Banco:BBVA Cuenta:0114254848 CLABE:012180001142548489",
            "TipoDeComprobante": "FA",
            "LABEL": "CABADD",
            "TIPO_DOC": "1",
            "CODIGO_FUF": \""""+f['FUF'][i]+"""\",
            "PERIODO_ECD":\""""+perecd2+"""\",
            "FECHA_LIM_PAGO":\""""+flimite2+"""\",
            "ID_PARTIC_CENACE":\""""+f['Participante'][i]+"""\",
            "BANCO": "BBVA",
            "SUCURSAL": "0031",
            "CUENTA": "0114254848",
            "CLABE": "012180001142548489",
            "REF_BANCO":\""""+f['FUF'][i]+"""\",
            "CONTACTO": "escuderop@xiix.mx",
            "NUM_LIN_0": "1",
            "LABEL_0": "LINADD",
            "FOLIO_UNICO_0":\""""+f['No. Identificacion'][i]+"""\",
            "NUM_LIN_1": "2",
            "LABEL_1": "LINADD",
            "FOLIO_UNICO_1":\""""+f['No. Identificacion'][i+1]+"""\"
          },
          "Comprobante": {
            "Exportacion":"01",
            "Serie": "Factura",
            "Folio":\""""+str(folio)+"""\",
            "Fecha":\""""+str(dia)+"""\",
            "SubTotal":\""""+str(round(f['Subtotal'][i]+f['Subtotal'][i+1],2))+"""\",
            "Moneda": "MXN",
            "Total":\""""+str(round(f['TOTAL'][i]+f['TOTAL'][i+1],2))+"""\",
            "TipoDeComprobante": "I",
            "FormaPago": "99",
            "MetodoPago": "PPD",
            "CondicionesDePago": "60 DIAS (TUA)",
            "Descuento":\""""+str(f['Descuento'][i])+"""\",
            "TipoCambio": "1",
            "LugarExpedicion": "05348",
            "Confirmacion":"" ,
            "Version": "4.0",
            "InformacionGlobal":{
                "Periodicidad":"",
                "Meses":"",
                "Anio":""
            },
            "CfdiRelacionados":[
                {
                    "TipoRelacion":"",
                    "CfdiRelacionado":[
                        {"UUID":""},
                        {"UUID":""}
                        
                    ]
                },
                {
                    "TipoRelacion":"",
                    "CfdiRelacionado":[
                        {"UUID":""}
                    ]
                }
            ],
            "Emisor": {
              "Rfc": "XTS191120H32",
              "Nombre": "XIIX TRADING SOLUTIONS",
              "RegimenFiscal": "601"
            },
            "Receptor": {
              "email":"",
              "numInt":"",
              "municipio": "ALVARO OBREGON",
              "colonia": "LOS ALPES",
              "estado": "MEXICO",
              "calle": "BOULEVARD ADOLFO LOPEZ MATEOS",
              "pais": "MEX",
              "Rfc": "CNC140828PQ4",
              "Nombre": "CENTRO NACIONAL DE CONTROL DE ENERGIA",
              "ResidenciaFiscal":"",
              "NumRegIdTrib":"",
              "UsoCFDI": "G01",
              "Pais": "MEX",
              "Estado": "MEXICO",
              "Municipio": "ALVARO OBREGON",
              "codigoPostal": "01010",
              "Colonia": "LOS ALPES",
              "NumInt": "",
              "noExterior": "2157",
              "Calle": "BOULEVARD ADOLFO LOPEZ MATEOS",
              "RegimenFiscalReceptor":"603",
              "DomicilioFiscalReceptor":"01010"
              
              
              
            },
            "Conceptos": {
              "Concepto": [
                {
                  "ClaveProdServ": "83101800",
                  "NoIdentificacion":\""""+f['No. Identificacion'][i]+"""\",
                  "ClaveUnidad":\""""+f['ClaveUnidad'][i]+"""\",
                  "Unidad": \""""+f['Unidad'][i]+"""\",
                  "Descripcion": \""""+f['Descripcion'][i]+"""\",
                  "Importe": \""""+str(f['Importe'][i])+"""\",  
                  "Cantidad": \""""+str(f['Cantidad'][i])+"""\",
                  "ValorUnitario": \""""+str(f['Precio Unitario'][i])+"""\",
                  "Descuento":\""""+str(f['Descuento'][i])+"""\" ,
                  "ObjetoImp":"02",
                  "Impuestos": {
                    "Traslados": {
                      "Traslado": [
                        {
                          "Impuesto": "002",
                          "TasaOCuota": "0.160000",
                          "Importe": \""""+str(f['IVA'][i])+"""\",
                          "TipoFactor":"Tasa",
                          "Base": \""""+str(f['Importe'][i])+"""\"
                        }
                      ]
                    },
                    "Retenciones": {
                      "Retencion": []
                    }
                  },
                  "InformacionAduanera": null
                },
                {
                  "ClaveProdServ": "83101800",
                  "NoIdentificacion":\""""+f['No. Identificacion'][i+1]+"""\",
                  "ClaveUnidad":\""""+f['ClaveUnidad'][i+1]+"""\",
                  "Unidad": \""""+f['Unidad'][i+1]+"""\",
                  "Descripcion": \""""+f['Descripcion'][i+1]+"""\",
                  "Importe": \""""+str(f['Importe'][i+1])+"""\",  
                  "Cantidad": \""""+str(f['Cantidad'][i+1])+"""\",
                  "ValorUnitario": \""""+str(f['Precio Unitario'][i+1])+"""\",
                  "Descuento":\""""+str(f['Descuento'][i+1])+"""\" ,
                  "ObjetoImp":"02",
                  "Impuestos": {
                    "Traslados": {
                      "Traslado": [
                        {
                          "Impuesto": "002",
                          "TasaOCuota": "0.160000",
                          "Importe": \""""+str(f['IVA'][i+1])+"""\",
                          "TipoFactor":"Tasa",
                          "Base": \""""+str(f['Importe'][i+1])+"""\"
                        }
                      ]
                    },
                    "Retenciones": {
                      "Retencion": []
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
        }
        """
        #bbody=json.loads(body)
        #print(body)
        #url='https://clickfactura.com.mx/clientes/'
        url='https://clickfactura.com.mx/api/timbrado/xml33/timbradorest/'
        heads={ 
            'Content-Type': 'application/json'
            }
        print(body)
        
        print("")
        print('¿Es correcta la factura?')
        val=input('y/n:')
        if val=='y':
            response=requests.post(url,data=body, headers=heads)
            print(response)
            try:
                import base64 as _b64, xml.etree.ElementTree as _ET, os as _os, csv as _csv
                rj = response.json()
                xml_b64 = rj.get('message', {}).get('xmlData', '')
                uuid = ''
                if xml_b64:
                    xml_str = _b64.b64decode(xml_b64).decode('utf-8')
                    root = _ET.fromstring(xml_str)
                    tfd = root.find('.//{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital')
                    uuid = tfd.get('UUID') if tfd is not None else ''
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
                print(f'Advertencia: no se pudo guardar UUID ({_ex})')
            print('OK')
        if val=='n':
            print('=================================================')
            
            print("        Esta factura no se subió")
            
            print('=================================================')
            
            print("")
            print("Continuar con la siguiente: 1")
            print("Detener el proceso: 2")
            print("")
            ok=input("Continuar/Detener:")
            if ok=='1':
                print('=======================================')
                print("     Continuamos")
                print('=======================================')
                
            if ok=='2':
                print('=======================================')
                print("     Se detuvo el envío")
                print('=======================================')
                break