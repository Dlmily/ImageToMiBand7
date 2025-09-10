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
        self.num_colors = 0 # 0表示不进行颜色压缩
        self.output_path = None

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
            if self.num_colors > 0:
                # 获取调色板数据并添加到输出
                palette = img.getpalette()
                # PIL的调色板是RGB，需要转换为RGBA并存储为BGRA
                # 每个颜色项是3字节RGB，需要将其转换为4字节BGRA
                bgra_palette = bytearray()
                for i in range(0, len(palette), 3):
                    b = palette[i+2]
                    g = palette[i+1]
                    r = palette[i]
                    a = 0xFF # Alpha通道设置为不透明
                    bgra_palette.extend([b, g, r, a])
                output_data.extend(bgra_palette)
            output_data.extend(pixels)


            output_data.extend(footer)
            
            if self.output_path:
                output_path = self.output_path
            else:
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
        
        if self.num_colors > 0:
            img = img.quantize(colors=self.num_colors, method=Image.Quantize.FASTOCTREE) # 更改为FASTOCTREE
        return img

    def _get_pixels(self, img):
        pixels = bytearray()
        if self.num_colors > 0:
            # 调色板模式
            for index in img.getdata():
                pixels.append(index)
        else:
            # RGBA模式
            for r, g, b, a in img.getdata():
                pixels.extend([b, g, r, a])
        return pixels

    def _create_header(self, width, height):
        header = bytearray(18)
        if self.num_colors > 0:
            # Indexed color image
            header[1] = 1  # Color map type: 1 (color map included)
            header[2] = 1  # Image type: 1 (uncompressed, color-mapped image)
            header[3:5] = struct.pack('<H', 0)  # Color map origin
            header[5:7] = struct.pack('<H', self.num_colors)  # Color map length
            header[7] = 32  # Color map entry depth: 32 (RGBA)
            header[16] = 8  # Pixel depth: 8 bits per pixel (for indexed color)
        else:
            # RGBA image
            header[2] = 2  # Image type: 2 (uncompressed, RGB image)
            header[16] = 32  # Pixel depth: 32 bits per pixel (RGBA)
        
        header[12:14] = struct.pack('<H', width)
        header[14:16] = struct.pack('<H', height)
        header[17] = 0x20  # Image descriptor: top-left origin
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

            # 根据是否使用颜色压缩调整TGA头部的某些字段
            if self.num_colors > 0:
                data[5:7] = struct.pack("<H", self.num_colors)  # Color Map Length
            else:
                data[5:7] = struct.pack("<H", 256) # 原始值

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
    parser.add_argument('-o', '--output', help='输出文件路径（仅适用于单文件转换）')
    parser.add_argument('-b', '--batch', action='store_true', help='批量转换目录中的所有图片')
    parser.add_argument('-s', '--max-size', type=int, default=100, 
                       help='自定义最大尺寸限制（默认100）')
    parser.add_argument('-c', '--colors', type=int, default=0, 
                       help='颜色压缩数量（0表示不压缩，例如256）')
    args = parser.parse_args()
    
    converter = WorkingTGAConverter()
    converter.max_size = args.max_size
    converter.num_colors = args.colors
    converter.output_path = args.output
    
    if args.batch:
        converter.batch_pack(args.input)
    else:
        converter.pack(args.input)

if __name__ == '__main__':
    main()