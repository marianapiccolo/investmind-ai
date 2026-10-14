variable "ssh_public_key" {
  description = "Public Ed25519 SSH key. Never provide the private key."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^ssh-ed25519 [A-Za-z0-9+/=]+", trimspace(var.ssh_public_key)))
    error_message = "Provide the public Ed25519 key generated for InvestMind."
  }
}

variable "ssh_allowed_cidr" {
  description = "Your current public IPv4 address with a /32 prefix."
  type        = string
  nullable    = false

  validation {
    condition = (
      can(cidrnetmask(var.ssh_allowed_cidr)) &&
      can(regex("/32$", var.ssh_allowed_cidr))
    )
    error_message = "SSH must be restricted to one valid public IPv4 address ending in /32."
  }
}

variable "root_volume_size_gb" {
  description = "Root disk size. Docker data will initially live on this disk."
  type        = number
  default     = 20
  nullable    = false

  validation {
    condition = (
      var.root_volume_size_gb >= 20 &&
      var.root_volume_size_gb <= 60 &&
      floor(var.root_volume_size_gb) == var.root_volume_size_gb
    )
    error_message = "Choose a whole number from 20 to 60 GB."
  }
}
