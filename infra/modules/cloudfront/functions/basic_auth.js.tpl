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

    // Serve index.html for /experimental and /control directory paths (with or without a trailing slash).
    if (request.uri.startsWith("/experimental/") || request.uri.startsWith("/control/")) {
        if (request.uri.endsWith("/")) {
            request.uri += "index.html";
        } else if (!request.uri.split("/").pop().includes(".")) {
            request.uri += "/index.html";
        }
    }

    return request;
}
