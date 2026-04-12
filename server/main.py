"main-Datei unseres Servers"
import grpc
from concurrent import futures
from loguru import logger

import invoice_pb2_grpc

from repository import InvoiceRepository
from logic import InvoiceLogic
from router import InvoiceRouter

def serve():
    # Zuerst das Repository (der Datenspeicher)
    repo = InvoiceRepository()
    
    # Dann die Logik (sie bekommt das Repo übergeben)
    logic = InvoiceLogic(repo)
    
    # Dann der Router (er bekommt die Logik übergeben)
    router = InvoiceRouter(logic)
   
    # Erstelle den Server mit einem Thread-Pool (für parallele Anfragen)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Registriere deinen Router beim gRPC-System
    invoice_pb2_grpc.add_InvoiceServiceServicer_to_server(router, server)
    
    # Port festlegen -> Daten ohne Verschlüsselung (insecure)
    server.add_insecure_port('[::]:50051')
    
    logger.info("gRPC Server gestartet auf Port 50051...")
    server.start()
    
    # Warte, bis der Server beendet wird (z.B. durch Strg+C)
    server.wait_for_termination()

if __name__ == '__main__':
    serve()