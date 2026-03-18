generate-proto:
	docker run --rm \
	  -v $(PWD)/proto:/proto \
	  -v $(PWD)/flight-service/app/generated:/out/flight \
	  -v $(PWD)/booking-service/app/generated:/out/booking \
	  python:3.12-slim bash -c "\
	    pip install grpcio-tools==1.78.0 --quiet \
	      --trusted-host pypi.org \
	      --trusted-host pypi.python.org \
	      --trusted-host files.pythonhosted.org && \
	    python -m grpc_tools.protoc -I /proto \
	      --python_out=/out/flight \
	      --grpc_python_out=/out/flight \
	      /proto/flight.proto && \
	    python -m grpc_tools.protoc -I /proto \
	      --python_out=/out/booking \
	      --grpc_python_out=/out/booking \
	      /proto/flight.proto && \
	    sed -i 's/^import flight_pb2/from app.generated import flight_pb2/' \
	      /out/flight/flight_pb2_grpc.py \
	      /out/booking/flight_pb2_grpc.py"
