'use strict';
window.addEventListener('DOMContentLoaded', () => {
  const specURL = new URL('./openapi.json', document.baseURI);
  const state = document.getElementById('reference-state');
  const denyAuthenticationUI = () => ({
    components: { authorizeBtn: () => null, authorizationPopup: () => null }
  });
  function staticRequestOnly(request) {
    const target = new URL(request.url, document.baseURI);
    if ((request.method || 'GET').toUpperCase() !== 'GET' ||
        target.origin !== specURL.origin || target.pathname !== specURL.pathname ||
        target.search || target.hash) {
      throw new Error('Documentation is read-only. API execution is disabled.');
    }
    request.credentials = 'omit';
    request.headers = {};
    return request;
  }
  try {
    window.SwaggerUIBundle({
      url: './openapi.json',
      dom_id: '#swagger-ui',
      supportedSubmitMethods: [],
      tryItOutEnabled: false,
      persistAuthorization: false,
      validatorUrl: null,
      withCredentials: false,
      deepLinking: true,
      displayRequestDuration: false,
      defaultModelsExpandDepth: 1,
      defaultModelRendering: 'model',
      docExpansion: 'list',
      plugins: [denyAuthenticationUI],
      requestInterceptor: staticRequestOnly,
      onComplete: () => { state.textContent = 'Read-only reference · local specification loaded. No backend connection is used.'; }
    });
  } catch {
    state.textContent = 'The interactive document viewer could not load. Use the OpenAPI JSON or source-reference links above. API execution remains disabled.';
  }
});
