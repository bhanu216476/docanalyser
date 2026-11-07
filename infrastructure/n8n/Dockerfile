# ==============================================================================
# DocAnalyser n8n Automation Engine - Production Dockerfile
# ==============================================================================

FROM n8nio/n8n:1.60.1

USER root
# Ensure workspace and templates directory exists
RUN mkdir -p /opt/n8n-workflows && chown -R node:node /opt/n8n-workflows
COPY --chown=node:node *.json /opt/n8n-workflows/

USER node
EXPOSE 5678
