# Ollama Modelfiles for idea-generator

This directory contains Ollama Modelfiles for the idea-generator project's specialized LLM agents. These modelfiles provide deterministic, schema-enforced behavior for small LLMs (3-8B parameters) by embedding system prompts and tuned generation parameters.

## Available Modelfiles

### `summarizer.Modelfile`
- **Purpose**: Analyzes GitHub issues and generates structured summaries with quantitative metrics
- **Base Model**: `llama3.2:latest` (can be changed to any compatible model)
- **Parameters**:
  - `temperature: 0.3` - Low temperature for focused, deterministic output
  - `top_k: 20` - Restricts token sampling for consistency
  - `top_p: 0.8` - Nucleus sampling for quality
  - `num_ctx: 4096` - Context window for issue text
  - `repeat_penalty: 1.1` - Prevents repetitive output

### `grouping.Modelfile`
- **Purpose**: Clusters similar GitHub issue summaries into coherent idea groups
- **Base Model**: `llama3.2:latest` (can be changed to any compatible model)
- **Parameters**:
  - `temperature: 0.2` - Very low temperature for deterministic clustering
  - `top_k: 10` - Strict token sampling for structured output
  - `top_p: 0.7` - Conservative nucleus sampling
  - `num_ctx: 8192` - Larger context window for batch processing
  - `repeat_penalty: 1.15` - Stronger penalty to reduce repetition

## Building Custom Models

To use these modelfiles, you need to create Ollama models from them:

### 1. Build the summarizer model:
```bash
ollama create idea-generator-summarizer -f idea_generator/llm/modelfiles/summarizer.Modelfile
```

### 2. Build the grouping model:
```bash
ollama create idea-generator-grouping -f idea_generator/llm/modelfiles/grouping.Modelfile
```

### 3. Verify the models are available:
```bash
ollama list | grep idea-generator
```

You should see both models listed:
```
idea-generator-grouping    latest    abc123def456    1.5 GB    2 minutes ago
idea-generator-summarizer  latest    def456abc123    1.5 GB    2 minutes ago
```

## Using Custom Models

After building the models, configure your environment to use them:

### Option 1: Environment Variables
Edit your `.env` file:
```bash
IDEA_GEN_MODEL_GROUPING=idea-generator-grouping
IDEA_GEN_MODEL_SUMMARIZING=idea-generator-summarizer
```

### Option 2: CLI Arguments
Pass model names directly to commands:
```bash
idea-generator run \
  --github-repo owner/repo \
  --model-grouping idea-generator-grouping \
  --model-summarizing idea-generator-summarizer
```

## Customizing Modelfiles

### Changing the Base Model
To use a different base model, edit the `FROM` line in the modelfile:

```dockerfile
# Original
FROM llama3.2:latest

# Use a larger model
FROM llama3.2:8b

# Use a different model family
FROM mistral:latest
```

### Adjusting Parameters
Tune generation parameters for your specific use case:

- **Lower temperature (0.1-0.3)**: More deterministic, focused output
- **Higher temperature (0.5-0.8)**: More creative, diverse output
- **Smaller `top_k` (5-20)**: More conservative token selection
- **Larger `num_ctx` (8192-16384)**: More context for longer inputs (requires more VRAM)

### Modifying System Prompts
The system prompts are embedded directly in the modelfiles. To change the behavior:

1. Edit the `SYSTEM` section in the modelfile
2. Rebuild the model with `ollama create`
3. Test with your use case

**Important**: Keep schema requirements unchanged to maintain compatibility with the pipeline validation logic.

## Benefits of Using Modelfiles

### 1. **Consistency**
- System prompts are version-controlled and explicit
- Parameters are locked in, preventing drift between runs
- No need to manage separate prompt files

### 2. **Performance**
- Tuned parameters reduce hallucination and improve output quality
- Low temperature ensures deterministic behavior for reproducible results
- Optimized context windows balance performance and quality

### 3. **Portability**
- Models can be exported and shared as single units
- Easy to version and deploy across environments
- No runtime prompt injection needed

### 4. **Debugging**
- All configuration in one place
- Easy to compare different parameter sets
- Can create variants for A/B testing

## Updating Models

When you update a modelfile, you must rebuild the model for changes to take effect:

```bash
# Edit the modelfile
nano idea_generator/llm/modelfiles/grouping.Modelfile

# Rebuild the model (overwrites existing)
ollama create idea-generator-grouping -f idea_generator/llm/modelfiles/grouping.Modelfile

# Verify changes
ollama show idea-generator-grouping
```

## Fallback Behavior

The idea-generator CLI gracefully falls back to default models if custom modelfiles aren't built:

1. **If custom model names are configured but models don't exist**: Error with actionable message suggesting to build the models
2. **If no custom model names are configured**: Uses `llama3.2:latest` with prompts loaded from `idea_generator/llm/prompts/`
3. **If Ollama server is unreachable**: Clear error message with troubleshooting steps

## Troubleshooting

### Model Not Found
```
Error: model 'idea-generator-grouping' not found
```

**Solution**: Build the model first:
```bash
ollama create idea-generator-grouping -f idea_generator/llm/modelfiles/grouping.Modelfile
```

### Out of Memory
```
Error: not enough VRAM to load model
```

**Solutions**:
- Use a smaller base model (e.g., `llama3.2:3b` instead of `llama3.2:8b`)
- Reduce `num_ctx` in the modelfile
- Close other applications using GPU memory

### Invalid Parameters
```
Error: parameter 'temperature' must be between 0.0 and 2.0
```

**Solution**: Check parameter values in the modelfile and ensure they're within valid ranges.

## Further Reading

- [Ollama Modelfile Documentation](https://github.com/ollama/ollama/blob/main/docs/modelfile.md)
- [Ollama API Documentation](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [idea-generator Configuration Guide](../../README.md#advanced-configuration)
