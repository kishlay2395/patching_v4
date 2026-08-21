#!/bin/bash

# Update the packages to check if installed / updated.
packages=(
    kernel-headers
    kernel-tools
    kernel-libbpf
    kernel-devel
)

# Validating each package is installed / updated.
for pkg in "${packages[@]}"; do
  if sudo dnf list installed "$pkg" &>/dev/null;
  then
    echo "Updating the package $pkg..."
    sudo dnf update -y "$pkg"
  else
    echo "Installing the package $pkg..."
    sudo dnf install -y "$pkg"
  fi
done