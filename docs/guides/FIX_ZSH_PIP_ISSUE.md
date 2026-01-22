# 🔧 Deep Fix: zsh pip Installation Error

## Root Cause Identified

**The Problem:** You have a custom `pip` shell function in your zsh configuration that's intercepting the `pip` command. This function doesn't properly handle package names with brackets like `python-jose[cryptography]`.

**Evidence:**
```bash
$ type pip
pip is a shell function from zsh
```

The custom function is likely in your `~/.zshrc` or similar config file and is interfering with pip's argument parsing.

## ✅ Solutions (Choose One)

### Solution 1: Use `command pip` (Bypasses the function)

```bash
source venv/bin/activate
command pip install 'python-jose[cryptography]'
```

The `command` keyword tells zsh to use the actual pip binary instead of the function.

### Solution 2: Use `python -m pip` (Recommended - Most Reliable)

```bash
source venv/bin/activate
python -m pip install 'python-jose[cryptography]'
```

This completely bypasses any shell functions and directly calls pip as a Python module.

### Solution 3: Fix Your Custom pip Function

If you want to keep using `pip` directly, you need to update your custom function to handle brackets. Find it in your `~/.zshrc`:

```bash
# Find the function
grep -n "pip ()" ~/.zshrc

# Or check other config files
grep -n "pip ()" ~/.zprofile ~/.zshenv 2>/dev/null
```

Then update it to properly quote arguments:

```bash
pip () {
    local cmd="$1"
    shift
    if [[ "$cmd" == "install" ]]
    then
        local package="$1"
        local requires_311="mcpo"
        if [[ "$requires_311" == *"$package"* ]]
        then
            echo "🔧 Using Python 3.11 for $package (requires Python >=3.11)..."
            python3.11 -m pip "$cmd" "$@"
            return $?
        fi
    fi
    # FIX: Use python -m pip to avoid bracket issues
    python -m pip "$cmd" "$@"
}
```

## Quick Reference: Working Commands

```bash
# ✅ These all work:
python -m pip install 'python-jose[cryptography]'
command pip install 'python-jose[cryptography]'

# ❌ This fails due to custom function:
pip install 'python-jose[cryptography]'
```

## Complete Working Example

```bash
cd /Users/jumar.juaton/Documents/GitHub/siloq

# Create venv (if not exists)
python3 -m venv venv

# Activate
source venv/bin/activate

# Install (use one of these):
python -m pip install 'python-jose[cryptography]'
# OR
command pip install 'python-jose[cryptography]'

# Verify installation
python -c "from jose import jwt; print('✅ python-jose installed successfully')"
```

## Why This Happens

1. **Custom pip function:** Your zsh config has a wrapper function for pip
2. **Bracket expansion:** zsh with `extendedglob` enabled tries to interpret `[cryptography]` as a glob pattern
3. **Argument parsing:** The custom function's argument parsing doesn't handle brackets correctly
4. **Solution:** Bypass the function using `command` or `python -m pip`

## Permanent Fix (Optional)

If you want to always use the real pip in virtual environments, add this to your `~/.zshrc`:

```bash
# Use real pip in virtual environments
if [[ -n "$VIRTUAL_ENV" ]]; then
    alias pip='python -m pip'
    alias pip3='python3 -m pip'
fi
```

This makes `pip` automatically use `python -m pip` when you're in a virtual environment.
