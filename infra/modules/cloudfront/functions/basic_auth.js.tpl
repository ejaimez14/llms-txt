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

    // Map experimental preview directory requests to their index.html, since
    // default_root_object only applies to the distribution root.
    if (request.uri.startsWith("/experimental/") && request.uri.endsWith("/")) {
        request.uri += "index.html";
    }

    return request;
}
