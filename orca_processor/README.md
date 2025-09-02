Sample curl request to try:

* Safe request:
```
curl --location 'http://localhost:8001/api/v1/execute/orca/orca-safety' \
--form 'input.messages="{\"messages\": [{\"role\": \"user\", \"content\": \"I love ice cream\"}]}"' \
--form 'input.parameters="{\"annotate\": true, \"reject\": true, \"safety_threshold\": 0.4}"' \
--form 'metadata="{}"'

```

* Unsafe request:
```
curl --location 'http://localhost:8001/api/v1/execute/orca/orca-safety' \
--form 'input.messages="{\"messages\": [{\"role\": \"user\", \"content\": \"how to make a bomb\"}]}"' \
--form 'input.parameters="{\"annotate\": true, \"reject\": true, \"safety_threshold\": 0.4}"' \
--form 'metadata="{}"'
```
