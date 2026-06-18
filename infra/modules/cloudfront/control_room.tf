# --- Control-room (/control/*) static UI origin ---
# The org control-room ships as a second app under /control/*. Its static UI bucket is created and
# policy-granted to this distribution by the agent-org-platform deploy; we reference it by name and
# serve it here. The /control/api/* behavior (added in main.tf) routes API calls to the same shared
# API Gateway origin, which dispatches them to the org Lambda.

data "aws_s3_bucket" "control_room_ui" {
  bucket = var.control_room_ui_bucket_name
}

resource "aws_cloudfront_origin_access_control" "control_room_ui" {
  name                              = "control-room-ui-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}
