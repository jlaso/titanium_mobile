#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Project Compiler
#

import os, sys, re, shutil, random, time, base64

template_dir = os.path.abspath(os.path.dirname(sys._getframe(0).f_code.co_filename))
sys.path.append(os.path.join(template_dir,'../'))

from tiapp import *
import jspacker 
from csspacker import CSSPacker

ignoreFiles = ['.gitignore', '.cvsignore', '.DS_Store'];
ignoreDirs = ['.git','.svn','_svn', 'CVS'];

HEADER = """/**
 * Appcelerator Titanium Mobile
 * This is generated code. Do not modify. Your changes *will* be lost.
 * Generated code is Copyright (c) 2009-2010 by Appcelerator, Inc.
 * All Rights Reserved.
 */
#import <Foundation/Foundation.h>
"""

INTERFACE_HEADER= """
@interface ApplicationRouting : NSObject {
}
+ (NSData*) resolveAppAsset:(NSString*)path;
"""

IMPL_HEADER= """#import "ApplicationRouting.h"

extern NSData * decode64 (NSData * thedata); 
extern NSData * dataWithHexString (NSString * hexString);
extern NSData * decodeDataWithKey (NSData * thedata, NSString * key);

@implementation ApplicationRouting

"""

FOOTER ="""
@end
"""

random.seed(time.time())

def dequote(s):
	if s[0:1] == '"':
		return s[1:-1]
	return s
	
# TODO/FIXME
#
# - encryptor
# - modules
# - iphone dir
#
	
class Compiler(object):
	
	def __init__(self,project_dir,appid,name,deploytype,xcode,devicefamily,iphone_version):
		self.project_dir = project_dir
		self.project_name = name
		self.appid = appid
		self.iphone_dir = os.path.join(project_dir,'build','iphone')
		self.classes_dir = os.path.join(self.iphone_dir,'Classes')
		self.modules = []
		
		# for now, these are required
		self.defines = ['USE_TI_ANALYTICS','USE_TI_NETWORK','USE_TI_PLATFORM']

		tiapp_xml = os.path.join(project_dir,'tiapp.xml')
		ti = TiAppXML(tiapp_xml)
		sdk_version = os.path.basename(os.path.abspath(os.path.join(template_dir,'../')))
		
		if xcode:
			app_name = os.environ['FULL_PRODUCT_NAME']
			app_dir = os.path.join(os.environ['TARGET_BUILD_DIR'],os.environ['CONTENTS_FOLDER_PATH'])
		else:
			target = 'Debug'
			if deploytype == 'install':
				target = 'Release'
			app_name = name+'.app'
			app_folder_name = '%s-iphoneos' % target
			app_dir = os.path.abspath(os.path.join(self.iphone_dir,'build',app_folder_name,app_name))
		
		main_template_file = os.path.join(template_dir,'main.m')
		main_template = open(main_template_file).read()
		main_template = main_template.replace('__PROJECT_NAME__',name)
		main_template = main_template.replace('__PROJECT_ID__',appid)
		main_template = main_template.replace('__DEPLOYTYPE__',deploytype)
		main_template = main_template.replace('__APP_ID__',appid)
		main_template = main_template.replace('__APP_ANALYTICS__',ti.properties['analytics'])
		main_template = main_template.replace('__APP_PUBLISHER__',ti.properties['publisher'])
		main_template = main_template.replace('__APP_URL__',ti.properties['url'])
		main_template = main_template.replace('__APP_NAME__',ti.properties['name'])
		main_template = main_template.replace('__APP_VERSION__',ti.properties['version'])
		main_template = main_template.replace('__APP_DESCRIPTION__',ti.properties['description'])
		main_template = main_template.replace('__APP_COPYRIGHT__',ti.properties['copyright'])
		main_template = main_template.replace('__APP_GUID__',ti.properties['guid'])
		if deploytype=='development':
			main_template = main_template.replace('__APP_RESOURCE_DIR__',os.path.abspath(os.path.join(project_dir,'Resources')))
		else:
			main_template = main_template.replace('__APP_RESOURCE_DIR__','')

		print "[INFO] Titanium SDK version: %s" % sdk_version
		print "[INFO] iPhone Device family: %s" % devicefamily
		print "[INFO] iPhone SDK version: %s" % iphone_version
		
		main_template_out = os.path.join(self.iphone_dir,'main.m')	
		main_file = open(main_template_out,'w')
		main_file.write(main_template)
		main_file.close()
		
		if deploytype == 'production':
			version = ti.properties['version']
			# we want to make sure in debug mode the version always changes
			version = "%s.%d" % (version,time.time())
			ti.properties['version']=version

		resources_dir = os.path.join(project_dir,'Resources')
		iphone_resources_dir = os.path.join(resources_dir,'iphone')
		
		#FIXME: remove android and iphone Resources
		#FIXME: nib vs. xib in Resources
		
		# write out the updated Info.plist
		infoplist_tmpl = os.path.join(self.iphone_dir,'Info.plist.template')
		infoplist = os.path.join(self.iphone_dir,'Info.plist')
		if devicefamily!=None:
			appicon = ti.generate_infoplist(infoplist,infoplist_tmpl,appid,devicefamily)
		else:
			appicon = ti.generate_infoplist(infoplist,infoplist_tmpl,appid,'iphone')
			
		# copy the app icon to the build resources
		appicon_path = os.path.join(iphone_resources_dir,appicon)
		if not os.path.exists(appicon_path):
			appicon_path = os.path.join(resources_dir,appicon)
		if os.path.exists(appicon_path):
			shutil.copy(appicon_path, app_dir)
			
		if devicefamily!=None:
			xib = 'MainWindow_%s.xib' % devicefamily
		else:
			xib = 'MainWindow_iphone.xib'
		s = os.path.join(template_dir,xib)
		t = os.path.join(iphone_resources_dir,'MainWindow.xib')
		shutil.copy(s,t)
		
		# copy in any resources in our module like icons
		project_module_dir = os.path.join(project_dir,'modules','iphone')
		if os.path.exists(project_module_dir):
			self.copy_resources([project_module_dir],app_dir,False)
		
		print "[DEBUG] deploytype = %s" % deploytype
			
		if deploytype!='development':
			self.copy_resources([iphone_resources_dir,resources_dir],app_dir)

			defines_header = open(os.path.join(self.classes_dir,'defines.h'),'w')
			defines_header.write("// Warning: this is generated file. Do not modify!\n\n")
			defines_header.write("TI_VERSION=%s\n"%sdk_version)
			for sym in self.defines:
				defines_header.write("#define %s 1\n"%sym)
			defines_header.flush()
			
		else:
			print "[INFO] Skipping JS compile, running from simulator"
	
	def add_symbol(self,api):
		curtoken = ''
		for token in api.split("."):
			curtoken+=token+"."
			symbol = 'USE_TI_%s' % (curtoken.replace('.create','').replace('.','').upper())
			try:
				self.defines.index(symbol)
			except:
				self.defines.append(symbol)
			
	def extract_modules(self,out,symbol):
		for line in out.split(';'):
			self.extract_module_with_token('Titanium',line)
			self.extract_module_with_token('Ti',line)
			f = re.findall(r'%s\.(.*)'%symbol,line)
			if len(f) > 0:
				for sym in f:
					#print sym
					api = self.extract_api_line(sym)
					if api!=None: self.add_symbol(api)

	def extract_module_with_token(self,token,line):
		f = re.findall(r'%s\.(\w+)'%token,line)
		if len(f) > 0:
			for sym in f:
				# skip top level properties that aren't modules
				if sym in ['version','userAgent','name','include']:
					continue
				sym = self.clean_api_symbol(sym)
				if sym==None: continue
				try:
					self.modules.index(sym)
				except:	
					self.modules.append(sym)
					self.add_symbol(sym)
	
	def clean_api_symbol(self,line):
		if re.match(r'^([a-zA-Z0-9_\.]+)$',line)!=None:
			return line
		print "[DEBUG] rejecting API symbol: %s" % line
		return None

	def extract_api_line(self,line):
		# these are terminals that indicate that the symbol is complete
		for sym in ['(','}','=',',',' ',':',')','!','[','+','*','/','~','^','%']:
			index = line.find(sym)
			if index != -1:
				return self.extract_api_line(line[0:index])
		return self.clean_api_symbol(line)	

	def compile_js(self,file_contents):
		self.extract_modules(file_contents,'Titanium')
		self.extract_modules(file_contents,'Ti')
		
	def make_function_from_file(self,path,file):
		fp = os.path.splitext(path)
		basename = fp[0].replace(' ','_').replace('/','_').replace('-','_').replace('.','_').replace('+','_')
		ext = fp[1][1:]

		filetype = ''
		contents = ''

		if ext=='html':
			filetype = 'page'
		elif ext=='css':
			filetype = 'style'
		elif ext=='js':
			filetype = 'script'	

		file_contents = open(os.path.expanduser(file)).read()

		# minimize javascript, css files
		if ext == 'js':
			file_contents = jspacker.jsmin(file_contents)
			self.compile_js(file_contents)
		elif ext == 'css':
			packer = CSSPacker(file_contents)
			file_contents = packer.pack()

		data = str(file_contents).encode("hex")
		method = "dataWithHexString(@\"%s\")" % data
		return {'method':method,'path':path}
	
	def copy_resources(self,sources,target,write_routing=True):
		
		if write_routing:
			intf = open(os.path.join(self.classes_dir,'ApplicationRouting.h'),'w+')
			impf = open(os.path.join(self.classes_dir,'ApplicationRouting.m'),'w+')

			intf.write(HEADER)
			intf.write(INTERFACE_HEADER)

			impf.write(HEADER)
			impf.write(IMPL_HEADER)

			impf.write("+ (NSData*) resolveAppAsset:(NSString*)path;\n{\n")
			impf.write("     static NSMutableDictionary *map;\n")
			impf.write("     if (map==nil)\n")
			impf.write("     {\n")
			impf.write("         map = [[NSMutableDictionary alloc] init];\n")

			impf_buffer = ''
		
		if not os.path.exists(os.path.expanduser(target)):
			os.mkdir(os.path.expanduser(target))
			
		for source in sources:
			print "[DEBUG] copy resources from %s to %s" % (source,target)
			for root, dirs, files in os.walk(source):
				for name in ignoreDirs:
					if name in dirs:
						dirs.remove(name)	# don't visit ignored directories			  
				for file in files:
					if file in ignoreFiles:
						continue
					prefix = root[len(target):]
					from_ = os.path.join(root, file)			  
					to_ = os.path.expanduser(from_.replace(source, target, 1))
					to_directory = os.path.expanduser(os.path.split(to_)[0])
					if not os.path.exists(to_directory):
						os.makedirs(to_directory)
					fp = os.path.splitext(file)
					if len(fp)>1 and write_routing and fp[1] in ['.html','.js','.css']:
						path = prefix + os.sep + file
						path = path[1:]
						print "[DEBUG] compiling: %s" % from_
						metadata = self.make_function_from_file(path,from_)
						method = metadata['method']
						eq = path.replace('.','_')
						impf.write('         [map setObject:%s forKey:@"%s"];\n' % (method,eq))
					else:
						# only copy if different filesize or doesn't exist
						if not os.path.exists(to_) or os.path.getsize(from_)!=os.path.getsize(to_):
							print "[DEBUG] copying: %s to %s" % (from_,to_)
							shutil.copyfile(from_, to_)	
						
		if write_routing:
			impf.write("     }\n")
			impf.write("     return [map objectForKey:path];\n")
			impf.write('}\n')
			impf.write(impf_buffer)

			intf.write(FOOTER)
			impf.write(FOOTER)

			intf.close()
			impf.close()
		
if __name__ == "__main__":
	project_dir = os.path.expanduser("~/tmp/yoyoyo")
	appid = "com.appcelerator.yoyoyo"
	name = "Yo Yo Yo"
	deploytype = 'development'
	xcode = False
	c = Compiler(project_dir,appid,name,deploytype,xcode)
	
	