output "instance_id" {
  description = "EC2 instance ID for start, stop, and status operations."
  value       = aws_instance.demo.id
}

output "public_ip" {
  description = "Public IPv4. This can change after stopping and starting EC2."
  value       = aws_instance.demo.public_ip
}

output "public_dns" {
  description = "EC2 public DNS name. This can change with the public IPv4."
  value       = aws_instance.demo.public_dns
}

output "ssh_command" {
  description = "SSH command to run from the Mac after creating the server."
  value = format(
    "ssh -i ~/.ssh/investmind_demo ubuntu@%s",
    aws_instance.demo.public_ip
  )
}

output "vpc_id" {
  description = "Project-specific VPC."
  value       = aws_vpc.demo.id
}
