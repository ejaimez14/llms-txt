function handler(event) {
    var request = event.request;
    var headers = request.headers;
    var expected = "Basic ${base64_credentials}";

    if (!headers.authorization || headers.authorization.value !== expected) {
        return {
            statusCode: 401,
            statusDescription: "Unauthorized",
            headers: {
                "www-authenticate": { value: 'Basic realm="llms.txt Crawler"' }
            }
        };
    }

    // Serve index.html for static-UI directory paths so /experimental/<id> and /control/ resolve.
    // The control room's API lives under /control/api/* and must pass through to API Gateway untouched.
    var uri = request.uri;
    var isUiPath =
        uri.startsWith("/experimental/") ||
        (uri.startsWith("/control/") && !uri.startsWith("/control/api/"));
    if (isUiPath) {
        if (uri.endsWith("/")) {
            request.uri += "index.html";
        } else if (!uri.split("/").pop().includes(".")) {
            request.uri += "/index.html";
        }
    }

    return request;
}
