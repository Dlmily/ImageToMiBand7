import os
import struct
from PIL import Image
import argparse

class WorkingTGAConverter:
    def __init__(self):
        self.color_map_list = []
        self.image_width = 0
        self.original_size = (0, 0)
        self.max_size = 100

    def pack(self, input_file):
        try:
            # 预处理图像
            img = Image.open(input_file)
            img = self._preprocess_image(img)
            
            # 生成TGA结构
            header = self._create_header(img.width, img.height)
            pixels = self._get_pixels(img)
            footer = self._create_footer()
            
            output_data = bytearray()
            output_data.extend(header)
            output_data.extend(pixels)
            output_data.extend(footer)
            
            output_path = os.path.splitext(input_file)[0] + '_watchface.png'
            with open(output_path, 'wb') as f:
                f.write(output_data)
            
            # 调用修复函数
            self.image_width = img.width
            self._image_fix(output_path)
                
            print(f"转换成功: {output_path}")
            return True
            
        except Exception as e:
            print(f"转换失败: {str(e)}")
            return False

    def batch_pack(self, input_dir):
        if not os.path.isdir(input_dir):
            print(f"错误: {input_dir} 不是有效目录")
            return False
        
        success_count = 0
        for filename in os.listdir(input_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                file_path = os.path.join(input_dir, filename)
                if self.pack(file_path):
                    success_count += 1
        
        print(f"批量转换完成，共成功转换 {success_count} 张图片")
        return success_count > 0

    def _preprocess_image(self, img):
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        self.original_size = img.size
        width, height = img.size
        if width > self.max_size or height > self.max_size:
            ratio = min(self.max_size/width, self.max_size/height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            img = img.resize((new_width, new_height))
        
        return img

    def _get_pixels(self, img):
        pixels = bytearray()
        for r, g, b, a in img.getdata():
            pixels.extend([b, g, r, a])
        return pixels

    def _create_header(self, width, height):
        header = bytearray(18)
        header[2] = 2
        header[12:14] = struct.pack('<H', width)
        header[14:16] = struct.pack('<H', height)
        header[16] = 32
        header[17] = 0x20
        return header

    def _create_footer(self):
        return bytes([
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x54, 0x52, 0x55, 0x45, 0x56, 0x49, 0x53, 0x49,
            0x4F, 0x4E, 0x2D, 0x58, 0x46, 0x49, 0x4C, 0x45,
            0x2E, 0x00
        ])

    def _image_fix(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                data = bytearray(f.read())

            header_end = 18
            new_description = bytearray(46)
            new_description[0:4] = [0x53, 0x4F, 0x4D, 0x48]
            new_description[4:6] = struct.pack('<H', self.image_width)
            new_description[6:8] = struct.pack('<H', self.original_size[0])
            new_description[8:10] = struct.pack('<H', self.original_size[1])

            data[0] = 46
            data[5:7] = struct.pack('<H', 256)
            data[7] = 32

            new_data = bytearray()
            new_data.extend(data[:18])
            new_data.extend(new_description)
            new_data.extend(data[18:-26])
            new_data.extend(self._create_footer())

            with open(file_path, 'wb') as f:
                f.write(new_data)

        except Exception as e:
            print(f"修复图像时出错: {str(e)}")
            raise

def main():
    parser = argparse.ArgumentParser(description='小米手环7表盘转换工具')
    parser.add_argument('input', help='输入PNG文件路径或目录路径')
    parser.add_argument('-b', '--batch', action='store_true', help='批量转换目录中的所有图片')
    parser.add_argument('-s', '--max-size', type=int, default=100, 
                       help='自定义最大尺寸限制（默认100）')
    args = parser.parse_args()
    
    converter = WorkingTGAConverter()
    converter.max_size = args.max_size
    
    if args.batch:
        converter.batch_pack(args.input)
    else:
        converter.pack(args.input)

if __name__ == '__main__':
    main()