variable "project_name" { type = string }
variable "environment" { type = string }
variable "domain_name" { type = string }

resource "aws_s3_bucket" "site" {
  bucket = "${var.project_name}.site"

  tags = {
    Name    = "${var.project_name}.site"
    Purpose = "CommandBridge portal static hosting"
  }
}

resource "aws_s3_bucket_public_access_block" "site" {
  bucket = aws_s3_bucket.site.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "site" {
  name                              = "${var.project_name}-oac"
  description                       = "CommandBridge S3 origin access control"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# CloudFront Function: SPA routing
# Rewrites non-file paths to /index.html for React Router.
# KB is now handled by React (dynamic DynamoDB-backed), not static MkDocs.
resource "aws_cloudfront_function" "spa_rewrite" {
  name    = "${var.project_name}-spa-rewrite"
  runtime = "cloudfront-js-2.0"
  publish = true
  code    = <<-EOF
    function handler(event) {
      var request = event.request;
      var uri = request.uri;
      // Let files with extensions pass through (JS, CSS, images, etc.)
      if (uri.includes('.')) {
        return request;
      }
      // SPA fallback: rewrite to index.html for React Router
      request.uri = '/index.html';
      return request;
    }
  EOF
}

# CloudFront Function: Security headers
# Adds security headers to all viewer responses.
resource "aws_cloudfront_function" "security_headers" {
  name    = "${var.project_name}-security-headers"
  runtime = "cloudfront-js-2.0"
  publish = true
  code    = <<-EOF
    function handler(event) {
      var response = event.response;
      var headers = response.headers;
      headers['strict-transport-security'] = { value: 'max-age=63072000; includeSubDomains; preload' };
      headers['x-content-type-options']    = { value: 'nosniff' };
      headers['x-frame-options']           = { value: 'DENY' };
      headers['referrer-policy']           = { value: 'strict-origin-when-cross-origin' };
      headers['content-security-policy']   = { value: "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' https://*.amazonaws.com https://*.amazoncognito.com; frame-ancestors 'none';" };
      return response;
    }
  EOF
}

resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  comment             = "CommandBridge portal (${var.environment})"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"

  origin {
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_id                = "s3-site"
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3-site"
    viewer_protocol_policy = "redirect-to-https"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.spa_rewrite.arn
    }

    function_association {
      event_type   = "viewer-response"
      function_arn = aws_cloudfront_function.security_headers.arn
    }

    min_ttl     = 0
    default_ttl = 300
    max_ttl     = 86400
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Name    = "CommandBridge CDN"
    Purpose = "CommandBridge portal distribution"
  }
}

# S3 bucket policy: allow CloudFront OAC only
data "aws_iam_policy_document" "site_bucket" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.site.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.site.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "site" {
  bucket = aws_s3_bucket.site.id
  policy = data.aws_iam_policy_document.site_bucket.json
}

output "cloudfront_domain" {
  value = aws_cloudfront_distribution.site.domain_name
}

output "bucket_name" {
  value = aws_s3_bucket.site.bucket
}

output "distribution_id" {
  value = aws_cloudfront_distribution.site.id
}
