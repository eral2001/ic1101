# Honda Civic APK Rebuilder
Script to quickly reconstruct full .apk files from 10th generation Honda Civic `MRC<...>.zip` update files.

## Requirements
- A Honda Civic update file; I can't host it here directly
- A recent version of Java (I'm using `openjdk 21.0.7-ea 2025-04-15`)
- A recent version of Python, >= Python 3.10+ (I'm using `Python 3.13.3`)

## Usage
1. Find a 10th generation Honda Civic update file on the internet. For copyright reasons I'm not linking it directly, but it should be easy to find. The filename looks something like this: `MRC<...>.zip` (where `<...>` contains version info)
2. Ensure you have Java installed (see requirements)
3. Ensure you have Python installed (see requirements)
4. Clone this repo and cd into the same directory as this README.md file.
5. Copy your update file somewhere accessible. I use `./inputs/MRC<...>.zip`, relative to this directory.
6. Run `python3 main.py ./inputs/MRC<...>.zip` (I'm on Linux; the specific syntax may vary if you're on Windows)
7. If all goes well, you'll have nice `.apk` files in the `./build/output-vendor-apps/` directory
8. Install the [jadx GUI tool](https://github.com/skylot/jadx)
9. In the JADX GUI, click `File` > `Open project` and select the `./build/output-vendor-apps/` directory.
10. When prompted to "Load all files from directory?" choose "Yes".

Now inside JADX on the left-side pane you should be able to expand `Source code` and find the Mitsubishi
source code under `Source code` > `com` > `mitsubishielectric.ada`. If you got this far, congrats! If you had trouble, create an issue or make a PR so I can address it and make this script better for everyone.

Running the script from start to finish should only take a minute or two.

## Compatibility
I tried to make this script compatible cross-platform. At the time of writing I've only tested in on Debian Linux, but it's an intentionally lean Python script that has no dependencies beyond the Python standard library and relies on standard library tools for things like path and file manipulations.

## JADX GUI Screenshot
![JADX GUI with Java source code hierarchy](./jadx-gui-screenshot.png)

## Motivation
If you want to view the source code for the vendor apps on the headunit, it's kind of a pain.
Without a script, you have to do the following:
- Find and download the `MRC<...>.zip` file on the internet
- Extract the `MRC<...>.zip` file
- Within the extracted file contents, locate the `SwUpdate.mdt` file
- Extract the `SwUpdate.mdt` file (it's just a zip archive itself)
- Download the [smali and baksmali .jar files](https://bitbucket.org/JesusFreke/smali/downloads/)
- Ensure that you have Java installed
- Then for each .apk in your extracted `system/vendor/app` directory:
  - Run `java -jar baksmali-2.5.2.jar ... SomeApp.odex` to produce .smali files
  - Run `java -jar smali-2.5.2.jar ...  -o classes.dex` to produce a classes.dex file
  - Rebuild `SomeApp.apk` using the original `system/vendor/app/SomeApp.apk` and the classes.dex file
- Use the [jadx GUI tool](https://github.com/skylot/jadx) to view source code from the resulting APK files

This is a lot of effort and there are also some non-trivial things you need to pass to those .jar files
to ensure that everything baksmalis correctly (e.g., you need to point to the `system/framework` and `system/vendor/framework` directories). This is time-consuming, error-prone and less reproducible by others.

By having a script automate this process, I hope other devs can get up to speed quickly with the headunit code.

## Using apktool alongside JADX

JADX is great for constructing Java code; apktool is better for resource resolution.

- I wanted to reverse-engineer the layouts from the vendor APKs in `/system/vendor/app/*.apk`
- I tried to use JADX to extract the resources
- In compiled APKs, all resources are stored as 32-bit integer IDs, not symbolic names
- When JADX decompiles the APK, it needs to map integer IDs back to symbolic names
- JADX does this by using a resource table, either from the APK itself or from a framework reference
- But Honda's framework-res.apk has custom resources with IDs that don't match standard Android
- So when JADX sees a resource ID like `0x108129a` it either:
	- Can't find it at all, shows the raw hex ID `0x108129a`
	- Finds a different resource in modern Android SDK that happens to have the same ID
		- Shows wrong name like `?android:attr/collapseContentDescription`
- In reality, `0x108129a` is a reference to a drawable defined in Honda's `framework-res.apk`
- JADX isn't correctly resolve the resource ID because it doesn't use framework-res.apk properly
- JADX uses hard-coded resource resolution w/ [jadx-core/src/main/resources/android/res-map.txt](https://github.com/skylot/jadx/blob/331c4aaa5ef0c6aa97fefafd1a818d5467040bd2/jadx-core/src/main/resources/android/res-map.txt)
- This means there are two underlying issues with resource resolution in JADX:
	- JADX maps resource IDs to resources that only exist in newer (> API 17) Android versions
		- So I would see a resource mapped to a resource string that was anachronistic
	- JADX does not know about custom resources in framework-res, so it fails to look up resource IDs
		- So I would just see a raw 32-bit hex value, representing the resource ID itself
- Apktool solved these symbol resolution issues because it can use a custom framework-res.apk
- Apktool decodes APK resources (layouts, drawables, values, manifest) to their original XML/file form
- I got the latest from https://apktool.org/
- At the time of writing this is `apktool_2.12.1.jar`
- Apktool produced better results than JADX

#### Apktool and Custom `framework-res.apk`
- I solved the resource resolution issues by installing `framework-res.apk` as a framework named `honda`
- Then I was able to unpack the resources for a given vendor app (here, `AirCon.apk`)
- This is now automated to unpack resources for all vendor apps
```
apktool if system/vendor/framework/framework-res.apk -t honda  
# I: Framework installed to: /home/user/.local/share/apktool/framework/1-honda.apk
java -jar apktool_2.12.1.jar d system/vendor/app/AirCon.apk -t honda -o AirCon-resources/
# I: Using Apktool 2.12.1 on AirCon.apk with 8 threads
# I: Loading resource table...
# I: Decoding file-resources...
# I: Loading resource table from file: /home/user/.local/share/apktool/framework/1-honda.apk
# I: Decoding values */* XMLs...
# I: Decoding AndroidManifest.xml with resources...
# I: Copying original files...
# I: Copying unknown files...
```
## Legal Notice
I am *NOT* affiliated with Honda Motor Co., Ltd. I am *NOT* affiliated with Mitsubishi. Honda and Honda Civic are registered trademarks. This repo does *NOT* contain proprietary APK files, source code, or software update files. This script is just a way to leverage existing tools and software update files that have been published elsewhere to produce .apk files locally.
