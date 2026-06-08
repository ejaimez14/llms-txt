function handler(event) {
    var request = event.request;
    var authHeader = request.headers['authorization'];

    if (!authHeader || authHeader.value !== 'Basic ${base64_credentials}') {
        return {
            statusCode: 401,
            statusDescription: 'Unauthorized',
            headers: {
                'www-authenticate': { value: 'Basic realm="llms-txt"' }
            }
        };
    }

    return request;
}
