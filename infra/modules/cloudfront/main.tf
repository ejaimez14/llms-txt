resource "random_id" "suffix" {
  byte_length = 4
}

resource "random_password" "api_key" {
  length  = 32
  special = false
}

# Injected as the x-api-key origin header on the RemodelAPI origin so the browser never holds it;
# the remodel authorizer only confirms the request arrived via this distribution.
resource "random_password" "remodel_api_key" {
  length  = 32
  special = false
}

resource "aws_s3_bucket" "frontend" {
  bucket = "llms-txt-frontend-${random_id.suffix.hex}"
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "llms-txt-frontend-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.frontend.arn}/*"
      Condition = {
        StringEquals = {
          "AWS:SourceArn" = aws_cloudfront_distribution.app.arn
        }
      }
    }]
  })
}

resource "aws_cloudfront_function" "basic_auth" {
  name    = "llms-txt-basic-auth"
  runtime = "cloudfront-js-2.0"
  publish = true
  code = templatefile("${path.module}/functions/basic_auth.js.tpl", {
    base64_credentials = base64encode("${var.basic_auth_user}:${var.basic_auth_password}")
  })
}

resource "aws_cloudfront_distribution" "app" {
  enabled             = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100"

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "S3Frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  origin {
    domain_name = trimsuffix(replace(var.api_gateway_endpoint, "https://", ""), "/")
    origin_id   = "APIGateway"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }

    custom_header {
      name  = "x-api-key"
      value = random_password.api_key.result
    }
  }

  origin {
    domain_name              = data.aws_s3_bucket.control_room_ui.bucket_regional_domain_name
    origin_id                = "ControlRoomUI"
    origin_access_control_id = aws_cloudfront_origin_access_control.control_room_ui.id
  }

  # Remodel Studio API — its own API Gateway in the remodel-studio stack. The SPA reuses the
  # S3Frontend origin under the studio/ key prefix, so no extra frontend origin is needed.
  origin {
    domain_name = trimsuffix(replace(var.remodel_api_endpoint, "https://", ""), "/")
    origin_id   = "RemodelAPI"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }

    custom_header {
      name  = "x-api-key"
      value = random_password.remodel_api_key.result
    }
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3Frontend"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.basic_auth.arn
    }

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }
  }

  ordered_cache_behavior {
    path_pattern           = "/api/*"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "APIGateway"
    viewer_protocol_policy = "https-only"

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.basic_auth.arn
    }

    forwarded_values {
      query_string = true
      headers      = ["Content-Type"]
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0
  }

  # Control-room API → shared API Gateway origin (dispatched to the org Lambda by the /control route).
  # Listed before /control/* so the more specific API path wins.
  ordered_cache_behavior {
    path_pattern           = "/control/api/*"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "APIGateway"
    viewer_protocol_policy = "https-only"

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.basic_auth.arn
    }

    forwarded_values {
      query_string = true
      headers      = ["Content-Type"]
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0
  }

  # Control-room static UI → its own S3 origin.
  ordered_cache_behavior {
    path_pattern           = "/control/*"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "ControlRoomUI"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.basic_auth.arn
    }

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }
  }

  # Remodel Studio API → its own API Gateway origin. Listed before /studio/* so the API path wins.
  ordered_cache_behavior {
    path_pattern           = "/studio/api/*"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "RemodelAPI"
    viewer_protocol_policy = "https-only"

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.basic_auth.arn
    }

    forwarded_values {
      query_string = true
      headers      = ["Content-Type"]
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0
  }

  # Remodel Studio SPA → shared frontend S3 bucket under the studio/ key prefix.
  ordered_cache_behavior {
    path_pattern           = "/studio/*"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3Frontend"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.basic_auth.arn
    }

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}
