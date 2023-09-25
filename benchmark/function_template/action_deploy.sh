# faas-cli deploy -f config.yml \
# --label com.openfaas.scale.max=10 \
# --label com.openfaas.scale.target=15 \
# --label com.openfaas.scale.type=cpu \
# --label com.openfaas.scale.target-proportion=0.70 \
# --label com.openfaas.scale.zero=true \
# --label com.openfaas.scale.zero-duration=30m \

# faas-cli deploy -f config.yml \
# --label com.openfaas.scale.max=10 \
# --label com.openfaas.scale.target=1 \
# --label com.openfaas.scale.type=capacity \
# --label com.openfaas.scale.target-proportion=0.95 \
# --env max_inflight=1


    
# faas-cli deploy -f config.yml \
# --label com.openfaas.scale.max=10 \
# --label com.openfaas.scale.target=50 \
# --label com.openfaas.scale.type=rps \
# --label com.openfaas.scale.target-proportion=0.90 \
# --label com.openfaas.scale.zero=true \
# --label com.openfaas.scale.zero-duration=10m


# faas-cli deploy -f config.yml && kubectl apply -f autoscale.yml && python update_gpu.py

faas-cli deploy -f config.yml