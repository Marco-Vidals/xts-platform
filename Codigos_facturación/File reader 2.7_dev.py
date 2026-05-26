# -*- coding: utf-8 -*-
"""
Created on Thu Jul 20 15:42:29 2023

This program extracts data from the EDCs to make the facturas
Don't make changes to this one as this is backup. 2.8 is the one in production
Use this one for normal facturación

@author: xiixt
"""
import numpy as np
import csv
import os
import time
import pandas as pd
from pandas.tseries.offsets import DateOffset, Week
import unidecode
import datetime
from dotenv import load_dotenv

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_SCRIPT_DIR, "..", "Extractors", ".env"))
BASE_FAC = os.environ.get(
    "FACTURACION_BASE",
    os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "Facturacion"))
)



# This function returns a list of filepaths with all the ECDs between a date range
def file_list(start_date, end_date):
    #Las cuentas de orden que se consideran para los paths, modificar si es necesario
    # cuenta_orden = ['SIN-M024ILA','SIN-M024IRD']
    
    cuenta_orden = ['BCA-M024ERO','BCA-M024ETJ','BCA-M024IRO','BCA-M024ITJ','SIN-M024EGT','SIN-M024ELA',
      'SIN-M024ERD','SIN-M024IGT','SIN-M024ILA','SIN-M024IRD','SIN-M024TBF']
    
    file_list = []
    
    # Generate a list of dates between start_date and end_date
    dates = pd.date_range(start=start_date, end=end_date)
    dates = [date.to_pydatetime() for date in dates]
    
    #create a list of file paths with all the dates and the cuentas de orden
    for date in dates:
        year = str(date.year)
        month = str(date.month).zfill(2)
        day = str(date.day).zfill(2)
        for cuenta in cuenta_orden:
            file2 = os.path.join(BASE_FAC, year, month, day, f'EC{year}{month}{day}{cuenta}.csv')
            file_list.append(file2)
    
    return file_list


# Esta funcion regresa las partes importantes de cada estado de cuenta
def ECD_extraction(filepath): 
    """
    Esta funcion regresa las partes importantes de cada estado de cuenta
    cada parte regresa como un df. Returns 4 pandas dataframes one for facturas xiix, one for facturas cenace, one for liquidaciones xiix 
    , and one for reliquidaciones cenace
    """
    file = filepath
    first_item = []
    alldata = []
    fuls = []
    fufs = []
    
    with open(file, "r",encoding='utf-8') as file:
        # Create a CSV reader object
        reader = csv.reader(file)
        # Iterate over each row in the CSV file
        for row in reader:
            # Process the row data here
            first_item.append(str(row[0]))
            alldata.append([str(item) for item in row])
            # first_item.append(str(row[0]))
            # alldata.append([str(item) for item in row])
        first_item.append('FUF')
        first_item.append('2')  
            
        print("CSV file reading complete: "+str(file)[-53:-32])
    
    #Finds appearances of FULS and FUF
    for i in range(len(first_item)):
        if first_item[i] == 'FULS' and first_item[i+1][0] == '2':
            fuls.append(i)
        if first_item[i] == 'FUF' and first_item[i-1][0] == '2':
            fufs.append((i,first_item[i+1]))
    
    
    #----------------------------------------------------XiiX--------------------------------------
    
    #reading XiiX factura Original
    start_row = fuls[0]
    end_row = fufs[1][0]
    columns = alldata[start_row]
    
    # print(alldata[start_row+1:end_row])
    
    #Creating a DF with only the XiiX data 
    df1 = pd.DataFrame(alldata[start_row+1:end_row],columns=columns)
    
    #Creating a column with FUFs
    columna_fuf = pd.Series([fufs[0][1]]*len(df1),dtype = object)
    df1.insert(loc=1, column='FUF', value=columna_fuf)
    
    #Dropping non-zero totals
    df1['TOTAL'] = df1['TOTAL'].astype(float)
    df1 = df1[df1['TOTAL'] != 0]
    
    
    #---------------------------------------------------CENACE-------------------------------------------
    
    #reading CENACE factura Original
    start_row = fuls[1]
    end_row = fufs[2][0]
    columns = alldata[start_row]
    
    #Creating a DF with only the XiiX data 
    df2 = pd.DataFrame(alldata[start_row+1:end_row],columns=columns)
    
    #Creating a column with FUFs
    columna_fuf = pd.Series([fufs[1][1]]*len(df2),dtype = object)
    df2.insert(loc=1, column='FUF', value=columna_fuf)
    
    #Dropping non-zero totals
    df2['TOTAL'] = df2['TOTAL'].astype(float)
    df2 = df2[df2['TOTAL'] != 0]
    
    
    ####-----------------------------------------------------------------------------------------------------####
    ####----------------------------------------------RELIQUIDACIONES----------------------------------------####
    ####-----------------------------------------------------------------------------------------------------####
    
    #Data frames with the aggregates of the reliq section
    columnas = ['FULS', 'FUF', 'CONCEPTO_DE_PAGO', 'PRECIO', 'CANTIDAD', 'IMPORTE','IVA', 'TOTAL']
    
    
    df3_xiix = pd.DataFrame(columns=columnas)
    df4_cenace = pd.DataFrame(columns=columnas)
    
    for i in range(len(fuls)-2):
        index = i+2
        start_row = fuls[index]
        end_row = fufs[index+1][0]
        columns = alldata[start_row]
        if alldata[start_row-1][1] == 'XIIX TRADING SOLUTIONS, SAPI DE CV':
            df3 = pd.DataFrame(alldata[start_row+1:end_row],columns=columns)
            
            columna_fuf = pd.Series([first_item[start_row-1]]*len(df3),dtype = object)
            df3.insert(loc=1, column='FUF', value=columna_fuf)
            
            df3_xiix = pd.concat([df3_xiix, df3], axis=0)
            df3_xiix.reset_index(drop=True, inplace=True)
            
            
        if alldata[start_row-1][1] == 'CENTRO NACIONAL DE CONTROL DE ENERGIA':
            df4 = pd.DataFrame(alldata[start_row+1:end_row],columns=columns)
            columna_fuf = pd.Series([first_item[start_row-1]]*len(df4),dtype = object)
            df4.insert(loc=1, column='FUF', value=columna_fuf)
            df4_cenace = pd.concat([df4_cenace, df4], axis=0)
            df4_cenace.reset_index(drop=True, inplace=True)
            
    #Dropping non-zero totals
    df3_xiix['TOTAL'] = df3_xiix['TOTAL'].astype(float)
    df3_xiix = df3_xiix[df3_xiix['TOTAL'] != 0]
    #Dropping non-zero totals
    df4_cenace['TOTAL'] = df4_cenace['TOTAL'].astype(float)
    df4_cenace = df4_cenace[df4_cenace['TOTAL'] != 0]
    return df1, df2, df3_xiix, df4_cenace

    
hoy       = datetime.datetime.today()
end_dt    = hoy - datetime.timedelta(days=8)   # domingo de hace 2 semanas
start_dt  = end_dt - datetime.timedelta(days=6) # lunes de hace 2 semanas
start_date = start_dt.strftime('%Y-%m-%d')
end_date   = end_dt.strftime('%Y-%m-%d')
print(f"Rango: {start_date} al {end_date}")
filepaths = file_list(start_date, end_date)

# ── Verificación de archivos antes de procesar ────────────────────────────────
archivos_faltantes = [fp for fp in filepaths if not os.path.exists(fp)]

if archivos_faltantes:
    print("\n⚠️  ERROR: No se puede correr el script, faltan los siguientes archivos:")
    for fp in archivos_faltantes:
        print(f"   - {fp}")
    print(f"\nTotal faltantes: {len(archivos_faltantes)} de {len(filepaths)}")
    print("Por favor corre primero el ecuentadrop y el file sorter antes de continuar.")
    raise SystemExit(1)

print(f"✓ Todos los archivos presentes ({len(filepaths)}). Iniciando procesamiento...\n")
# ─────────────────────────────────────────────────────────────────────────────

columnas = ['FULS', 'FUF', 'CONCEPTO_DE_PAGO', 'CONCEPTO_DE_CARGO','PRECIO', 'CANTIDAD', 'IMPORTE','IVA', 'TOTAL']

#Los DataFrames de ECD XiiX y ECD CENACE
dfmainXiiX = pd.DataFrame(columns=columnas)
dfmainCENACE = pd.DataFrame(columns=columnas)
dfreliqXiiX = pd.DataFrame(columns=columnas)
dfreliqCENACE = pd.DataFrame(columns=columnas)



for filepath in filepaths:
    df1, df2, df3, df4 = ECD_extraction(filepath)
    #Appending to XiiX
    dfmainXiiX = pd.concat([dfmainXiiX, df1], axis=0)
    dfmainXiiX.reset_index(drop=True, inplace=True)
    #Appending to CENACE
    dfmainCENACE = pd.concat([dfmainCENACE, df2], axis=0)
    dfmainCENACE.reset_index(drop=True, inplace=True)
    #Appending to XiiX reliq
    dfreliqXiiX = pd.concat([dfreliqXiiX, df3], axis=0)
    dfreliqXiiX.reset_index(drop=True, inplace=True)
    #Appending to CENACE reliq
    dfreliqCENACE = pd.concat([dfreliqCENACE, df4], axis=0)
    dfreliqCENACE.reset_index(drop=True, inplace=True)
    time.sleep(.01)
    
def get_date(row):
    # Convert string to datetime
    date = pd.to_datetime(row)
    # Check if the date is already Sunday
    if date.weekday() != 6:
        # If not, find next Sunday
        offset = DateOffset(weekday=6)  # 6 means Sunday
        date = date + offset
    # Find next Wednesday after the Sunday
    offset = DateOffset(weekday=2)  # 2 means Wednesday
    next_wednesday = date + offset
    # Find the next Wednesday after the previous Wednesday
    final_date = next_wednesday + Week(weekday=2)
    return final_date

#Creando el formato de las notas de crédito/débito
columns_liq = ['Cantidad','Tipo','Folio Fiscal','ClaveUnidad','Unidad','No. Identificacion', 'ClaveSAT', 'Descripcion', 'Importe Original', 'Importe Modificado', 'Monto Ajuste', 
               'Obj. Impuesto', 'Precio Unitario', 'Importe', 'Periodo ECD','FUF', 'Fecha Limite de Pago','Participante' ,'Subtotal', 'Descuento', 'IVA',"Importe x .16"]

df_liq1 = dfreliqXiiX.iloc[::2].reset_index(drop=True)
df_liq2 = dfreliqXiiX.iloc[1::2].reset_index(drop=True)
xiix_liq = pd.DataFrame(columns=columns_liq)
xiix_liq['No. Identificacion'] = df_liq2['FULS']
xiix_liq['ClaveUnidad'] = 'ZZ'
xiix_liq['Unidad'] = 'Mutuamente definido'
xiix_liq['ClaveSAT'] = 83101800
xiix_liq['Tipo'] = (pd.to_numeric(df_liq2['TOTAL']) - pd.to_numeric(df_liq1['TOTAL'])).apply(lambda x: 'ND' if x > 0 else 'NC')
xiix_liq.reset_index(drop=True, inplace=True)
xiix_liq['Descripcion'] = df_liq2['CONCEPTO_DE_PAGO'] +' LIQ' + df_liq2['FUF'].str[-1:]
xiix_liq['Descripcion'] = xiix_liq['Descripcion'].str.upper()
xiix_liq['Descripcion'] = xiix_liq['Descripcion'].apply(lambda x: unidecode.unidecode(x))
xiix_liq['Importe Original'] = pd.to_numeric(df_liq1['IMPORTE']).abs()
xiix_liq['Importe Modificado'] = pd.to_numeric(df_liq2['IMPORTE']).abs()
xiix_liq['Monto Ajuste'] = (pd.to_numeric(df_liq2['IMPORTE'])-pd.to_numeric(df_liq1['IMPORTE'])).abs().round(2)
xiix_liq['Obj. Impuesto'] = '02'
xiix_liq['Precio Unitario'] = xiix_liq['Monto Ajuste'].round(2)
xiix_liq['Importe'] = xiix_liq['Monto Ajuste'].round(2)
xiix_liq['Periodo ECD'] = pd.to_datetime(df_liq2['FUF'].str[:-10], format = '%Y%m%d' )
xiix_liq['Periodo ECD'] = xiix_liq['Periodo ECD'].dt.strftime('%d/%m/%Y')
xiix_liq['FUF'] = df_liq2['FUF']
xiix_liq['Subtotal'] = xiix_liq['Monto Ajuste'].round(2)
xiix_liq['Descuento'] = '0.00'
xiix_liq['IVA'] = (pd.to_numeric(df_liq2['IVA'])-pd.to_numeric(df_liq1['IVA'])).abs().round(2)
# xiix_liq['TOTAL'] = (pd.to_numeric(df_liq2['TOTAL'])-pd.to_numeric(df_liq1['TOTAL'])).abs()
# Assume your dataframe is xiix_liq and the column is 'Periodo ECD'
xiix_liq['Periodo ECD'] = pd.to_datetime(xiix_liq['Periodo ECD'], format='%d/%m/%Y')
xiix_liq['Fecha Limite de Pago'] = xiix_liq['Periodo ECD'].apply(get_date)
xiix_liq['Fecha Limite de Pago'] = np.where(xiix_liq['Tipo'] == 'Credito', xiix_liq['Fecha Limite de Pago'] - pd.Timedelta(days=7), xiix_liq['Fecha Limite de Pago'])
xiix_liq['Fecha Limite de Pago'] = xiix_liq['Fecha Limite de Pago'].dt.strftime('%d/%m/%Y')
try:
    import pyodbc
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_SCRIPT_DIR, "..", "Extractors", ".env"))
    _conn = pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={os.environ.get('XTS_DB_SERVER','100.70.216.12')},{os.environ.get('XTS_DB_PORT','1433')};"
        f"DATABASE={os.environ.get('XTS_DB_NAME','XTS')};"
        f"UID={os.environ.get('XTS_DB_USER','sa')};"
        f"PWD={os.environ.get('XTS_DB_PASSWORD','')};"
        f"TrustServerCertificate=yes;"
    )
    lista_fufs = pd.read_sql("SELECT FUF, UUDI, SERIE, FOLIO FROM facturacion.lista_fuf", _conn)
    _conn.close()
    print(f"✓ LISTA_FUF cargada desde DB: {len(lista_fufs)} registros")
except Exception as _e:
    print(f"⚠️  DB no disponible ({_e}), usando Excel local como fallback")
    lista_fufs = pd.read_excel(os.path.join(BASE_FAC, 'Scripts', 'LISTA_FUF_XIIX.xlsx'))
lista_fufs.reset_index(drop=True, inplace=True)
xiix_liq['FUF_O'] = xiix_liq['No. Identificacion'].str[:8]+ xiix_liq['FUF'].str[8:16]+'00'
xiix_liq['Participante'] = xiix_liq['FUF'].str[8:15]
xiix_liq['Cantidad'] = '1.00'
xiix_liq["Importe x .16"] = xiix_liq['Importe']*.16
xiix_liq["Importe x .16"] = xiix_liq["Importe x .16"].round(2)
xiix_liq['TOTAL'] = xiix_liq['Importe'] + xiix_liq["Importe x .16"]

#Agregando los folios fiscales
for i in range(len(xiix_liq['FUF_O'])):
    for j in range(len(lista_fufs['FUF'])):
        if xiix_liq.loc[i,'FUF_O'] == lista_fufs.loc[j,'FUF']:
            xiix_liq.loc[i,'Folio Fiscal'] = lista_fufs.loc[j,'UUDI']

xiix_liq.drop('FUF_O',axis=1,inplace =True)



#Creando el formato de las facturas originales
df_facturas = dfmainXiiX
df_facturas['Cantidad'] = df_facturas['CANTIDAD']


for i in range(len(df_facturas['Cantidad'])):
    if df_facturas['Cantidad'][i] == '':
        df_facturas.loc[i,'Cantidad'] = -1
        
df_facturas['ClaveUnidad'] = 'MWH'

for i in range(len(df_facturas['ClaveUnidad'])):
    if df_facturas['Cantidad'][i] == -1:
        df_facturas.loc[i,'ClaveUnidad'] = 'ZZ'

df_facturas['Unidad'] = 'Megawatt hora'

for i in range(len(df_facturas['Unidad'])):
    if df_facturas['Cantidad'][i] == -1:
        df_facturas.loc[i,'Unidad'] = 'Mutuamente definido'
        


df_facturas.reset_index(drop=True, inplace=True)
df_facturas['No. Identificacion'] = df_facturas['FULS']
df_facturas['ClaveSAT'] = 83101800
df_facturas['Descripcion'] = df_facturas['CONCEPTO_DE_PAGO']
df_facturas['Descripcion'] = df_facturas['Descripcion'].str.upper()
df_facturas['Descripcion'] = df_facturas['Descripcion'].apply(lambda x: unidecode.unidecode(x))
df_facturas['Obj. Impuesto'] = '02'
df_facturas['Precio Unitario'] = df_facturas['PRECIO']

for i in range(len(df_facturas['Precio Unitario'])):
    if df_facturas['Cantidad'][i] == -1:
        df_facturas.loc[i,'Precio Unitario'] = df_facturas.loc[i,'IMPORTE']
        
        
for i in range(len(df_facturas['Cantidad'])):
    if df_facturas['Cantidad'][i] == -1:
        df_facturas.loc[i,'Cantidad'] = 1


df_facturas['Importe'] = df_facturas['IMPORTE']
df_facturas['Periodo ECD'] = pd.to_datetime(df_facturas['FUF'].str[:-10], format = '%Y%m%d' )
df_facturas['Periodo ECD'] = df_facturas['Periodo ECD'].dt.strftime('%Y-%m-%d')

#Fecha Limite de pago
df_facturas['Subtotal'] = df_facturas['IMPORTE']
df_facturas['Descuento'] = '0.00'
df_facturas['Periodo ECD'] = pd.to_datetime(df_facturas['Periodo ECD'], format='%Y-%m-%d')
df_facturas['Fecha Limite de Pago'] = df_facturas['Periodo ECD'].apply(get_date)
df_facturas['Fecha Limite de Pago'] = df_facturas['Fecha Limite de Pago'].dt.strftime('%Y-%m-%d')
df_facturas['Participante'] = df_facturas['FUF'].str[8:15]

needed_columns = ['Cantidad','ClaveUnidad','Unidad','No. Identificacion','ClaveSAT','Descripcion','Obj. Impuesto','Precio Unitario',
'Importe','Periodo ECD','FUF','Fecha Limite de Pago','Participante','Subtotal','Descuento','IVA','TOTAL']
df_facturas = df_facturas[needed_columns]


dfmainCENACE['DO'] = pd.to_datetime(dfmainCENACE['FUF'].str[:-10], format = '%Y%m%d' ) - pd.Timedelta(days = 7)
dfmainCENACE['DO'] = dfmainCENACE['DO'].dt.strftime('%d/%m/%Y')
dfmainCENACE['Cuenta de Orden'] = dfmainCENACE['FUF'].str[8:15]

# Haciendo el formato de internals para lo de los EDCs de XiiX
dfmainXiiX['DO'] = pd.to_datetime(dfmainXiiX['FUF'].str[:-10], format = '%Y%m%d' ) - pd.Timedelta(days = 7)
dfmainXiiX['DO'] = dfmainXiiX['DO'].dt.strftime('%d/%m/%Y')
dfmainXiiX['Cuenta de orden'] = dfmainXiiX['FUF'].str[8:15]
dfmainXiiX['FUL'] = dfmainXiiX['FULS']
dfmainXiiX['Concepto'] = dfmainXiiX['CONCEPTO_DE_PAGO']
dfmainXiiX['Precio'] = dfmainXiiX['PRECIO']
dfmainXiiX['Suma de Importe'] = dfmainXiiX['Importe']
dfmainXiiX['Suma de Total'] = dfmainXiiX['TOTAL']



df_main_xiix_internals = dfmainXiiX[['DO', 'Cuenta de orden','FUL','Concepto', 'Precio','Cantidad','Suma de Importe','IVA','Suma de Total']]
dfmainCENACEInternals = dfmainCENACE[['DO', 'Cuenta de Orden','FULS','CONCEPTO_DE_CARGO', 'PRECIO','CANTIDAD','IMPORTE','IVA','TOTAL']]


#Crear los CSVs de las facturas - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
df_facturas.to_csv(os.path.join(BASE_FAC, 'XiiXFacturas.csv'), encoding='utf-8', index=False)
xiix_liq.to_excel(os.path.join(BASE_FAC, 'XiiXNotas.xlsx'), index=False)




# dfmainCENACE.to_csv('C:\\Users\\xiixt\OneDrive - XIIX TRADING SOLUTIONS SAPI DE CV\\XTS R&D\\Facturacion\\CENACEfacturas.csv', encoding = 'windows-1252')
# dfmainCENACEInternals.to_csv('C:\\Users\\xiixt\OneDrive - XIIX TRADING SOLUTIONS SAPI DE CV\\XTS R&D\\Facturacion\\CENACEInternals.csv', encoding = 'windows-1252')
# df_main_xiix_internals.to_csv('C:\\Users\\xiixt\OneDrive - XIIX TRADING SOLUTIONS SAPI DE CV\\XTS R&D\\Facturacion\\xiix_internals.csv', encoding = 'windows-1252')


# dfreliqCENACE.to_csv('C:\\Users\\xiixt\\Documents\\Facturacion\\CENACEreliq.csv', encoding = 'windows-1252')
# dfreliqXiiX.to_csv('C:\\Users\\xiixt\\Documents\\Facturacion\\XiiXreliq.csv', encoding = 'windows-1252')
# dfmainXiiX.to_csv('C:\\Users\\xiixt\\Documents\\Facturacion\\XiiX.csv', encoding = 'windows-1252')

print()
print('Lista la creación de CSVs de facturas y notas de crédito/débito')
        
        
        
        
        
        
        
        

        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        