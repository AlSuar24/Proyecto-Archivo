import os
import getpass
from pypdf import PdfReader, PdfWriter


# ==========================================================
# MÓDULO 1: UNIFICACIÓN DE LEGAJO
# ==========================================================
class UnificacionLegajo:
    """Módulo para unir múltiples archivos PDF en un único legajo final."""

    @staticmethod
    def unir_legajo(directorio_origen: str, archivo_salida: str) -> None:
        if not os.path.isdir(directorio_origen):
            print(f"[Error] La carpeta especificada no existe: {directorio_origen}")
            return

        # Filtrar y ordenar alfabéticamente los PDFs
        archivos = sorted([
            f for f in os.listdir(directorio_origen) 
            if f.lower().endswith(".pdf")
        ])

        if not archivos:
            print("[Aviso] No se encontraron archivos PDF para unificar.")
            return

        escritor = PdfWriter()
        archivos_agregados = 0

        for nombre_archivo in archivos:
            ruta_completa = os.path.join(directorio_origen, nombre_archivo)
            try:
                lector = PdfReader(ruta_completa)
                if lector.is_encrypted:
                    print(f"[Omitido] '{nombre_archivo}' tiene contraseña. Desbloquéalo primero.")
                    continue

                for pagina in lector.pages:
                    escritor.add_page(pagina)

                print(f"[Añadido] {nombre_archivo}")
                archivos_agregados += 1
            except Exception as e:
                print(f"[Error] No se pudo procesar '{nombre_archivo}': {e}")

        if archivos_agregados > 0:
            with open(archivo_salida, "wb") as f_salida:
                escritor.write(f_salida)
            print(f"\n[Éxito] Legajo unificado generado correctamente en: {archivo_salida}")
        else:
            print("[Aviso] No se añadió ningún archivo al legajo final.")


# ==========================================================
# MÓDULO 2: GESTIÓN DE SEGURIDAD (QUITAR / AGREGAR CONTRASEÑA)
# ==========================================================
class GestorSeguridadPDF:
    """Módulo para remover o aplicar protección con contraseña de forma masiva."""

    @staticmethod
    def quitar_contrasena_masivo(carpeta_origen: str, carpeta_destino: str) -> None:
        if not os.path.isdir(carpeta_origen):
            print(f"[Error] Carpeta de origen no encontrada: {carpeta_origen}")
            return

        password = getpass.getpass("Ingrese la contraseña actual para desbloquear los PDFs: ")
        os.makedirs(carpeta_destino, exist_ok=True)

        archivos = [f for f in os.listdir(carpeta_origen) if f.lower().endswith(".pdf")]
        procesados = 0

        for archivo in archivos:
            ruta_entrada = os.path.join(carpeta_origen, archivo)
            ruta_salida = os.path.join(carpeta_destino, archivo)

            try:
                lector = PdfReader(ruta_entrada)
                if lector.is_encrypted:
                    estado = lector.decrypt(password)
                    if estado == 0:
                        print(f"[Fallo Clave] Contraseña incorrecta para: {archivo}")
                        continue

                escritor = PdfWriter()
                for pagina in lector.pages:
                    escritor.add_page(pagina)

                with open(ruta_salida, "wb") as f_out:
                    escritor.write(f_out)

                print(f"[Desprotegido] {archivo}")
                procesados += 1

            except Exception as e:
                print(f"[Error] No se pudo procesar '{archivo}': {e}")

        print(f"\n[Fin] Total de archivos desbloqueados: {procesados}/{len(archivos)}")

    @staticmethod
    def agregar_contrasena_masivo(carpeta_origen: str, carpeta_destino: str) -> None:
        if not os.path.isdir(carpeta_origen):
            print(f"[Error] Carpeta de origen no encontrada: {carpeta_origen}")
            return

        nueva_clave = getpass.getpass("Ingrese la nueva contraseña que desea aplicar a los PDFs: ")
        confirmacion = getpass.getpass("Confirme la contraseña: ")

        if nueva_clave != confirmacion:
            print("[Error] Las contraseñas no coinciden. Operación cancelada.")
            return

        os.makedirs(carpeta_destino, exist_ok=True)

        archivos = [f for f in os.listdir(carpeta_origen) if f.lower().endswith(".pdf")]
        procesados = 0

        for archivo in archivos:
            ruta_entrada = os.path.join(carpeta_origen, archivo)
            ruta_salida = os.path.join(carpeta_destino, archivo)

            try:
                lector = PdfReader(ruta_entrada)
                if lector.is_encrypted:
                    print(f"[Omitido] '{archivo}' ya está cifrado. Primero remueve su contraseña.")
                    continue

                escritor = PdfWriter()
                for pagina in lector.pages:
                    escritor.add_page(pagina)

                # Cifrado con algoritmo estándar AES-128
                escritor.encrypt(user_password=nueva_clave)

                with open(ruta_salida, "wb") as f_out:
                    escritor.write(f_out)

                print(f"[Protegido] {archivo}")
                procesados += 1

            except Exception as e:
                print(f"[Error] Fallo al proteger '{archivo}': {e}")

        print(f"\n[Fin] Total de archivos protegidos: {procesados}/{len(archivos)}")


# ==========================================================
# MENÚ DE CONSOLA INTERACTIVO
# ==========================================================
def menu_principal():
    while True:
        print("\n" + "=" * 45)
        print("          HERRAMIENTA GESTIÓN DE PDF         ")
        print("=" * 45)
        print("1. Unificación de Legajo (Combinar PDFs)")
        print("2. Quitar contraseña masivamente")
        print("3. Agregar contraseña masivamente")
        print("4. Salir")
        
        opcion = input("\nSeleccione una opción (1-4): ").strip()

        if opcion == "1":
            print("\n--- UNIFICACIÓN DE LEGAJO ---")
            origen = input("Ruta de la carpeta con los PDFs a unir: ").strip()
            salida = input("Nombre o ruta del archivo de salida (ej. legajo_completo.pdf): ").strip()
            UnificacionLegajo.unir_legajo(origen, salida)

        elif opcion == "2":
            print("\n--- REMOVER CONTRASEÑAS ---")
            origen = input("Ruta de la carpeta origen (con PDFs protegidos): ").strip()
            destino = input("Ruta de la carpeta de destino: ").strip()
            GestorSeguridadPDF.quitar_contrasena_masivo(origen, destino)

        elif opcion == "3":
            print("\n--- AGREGAR CONTRASEÑA ---")
            origen = input("Ruta de la carpeta origen (PDFs sin contraseña): ").strip()
            destino = input("Ruta de la carpeta de destino: ").strip()
            GestorSeguridadPDF.agregar_contrasena_masivo(origen, destino)

        elif opcion == "4":
            print("Cerrando la aplicación.")
            break
        else:
            print("Opción inválida. Intente de nuevo.")


if __name__ == "__main__":
    menu_principal()