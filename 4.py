import os
import struct
from PIL import Image
import argparse

class WorkingTGAConverter:
    def __init__(self):
        self.target_width = 240
        self.target_height = 240
        self.color_map_list = []
        self.image_width = 0

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

    def _preprocess_image(self, img):
        """图像预处理"""
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        if img.width != self.target_width or img.height != self.target_height:
            img = img.resize((self.target_width, self.target_height))
        
        return img

    def _get_pixels(self, img):
        """获取像素数据"""
        pixels = bytearray()
        for r, g, b, a in img.getdata():
            pixels.extend([b, g, r, a])
        return pixels

    def _create_header(self, width, height):
        """生成标准TGA头"""
        header = bytearray(18)
        header[2] = 2
        header[12:14] = struct.pack('<H', width)
        header[14:16] = struct.pack('<H', height)
        header[16] = 32  # 像素深度32位
        header[17] = 0x20
        return header

    def _create_footer(self):
        """标准TGA文件尾"""
        return bytes([
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x54, 0x52, 0x55, 0x45, 0x56, 0x49, 0x53, 0x49,
            0x4F, 0x4E, 0x2D, 0x58, 0x46, 0x49, 0x4C, 0x45,
            0x2E, 0x00
        ])

    def _image_fix(self, file_path):
        """修复图像"""
        try:
            with open(file_path, 'rb') as f:
                data = bytearray(f.read())
            
            image_id_length = data[0]
            color_map_count = struct.unpack('<H', data[5:7])[0]
            color_map_entry_size = data[7]
            header_end = 18
            
            image_description = data[header_end:header_end+image_id_length]
            
            color_map_offset = header_end + image_id_length
            color_map_length = (color_map_entry_size // 8) * color_map_count
            color_map = data[color_map_offset:color_map_offset+color_map_length]
            
            image_data_offset = color_map_offset + color_map_length
            image_data = data[image_data_offset:]
            
            data[0] = 46
            new_description = bytearray(46)
            new_description[0:4] = [0x53, 0x4F, 0x4D, 0x48]
            new_description[4:6] = struct.pack('<H', self.image_width)

            data[5:7] = struct.pack('<H', 256)
            data[7] = 32
            
            # 重建文件数据
            new_data = bytearray()
            new_data.extend(data[:18])  # 头部
            new_data.extend(new_description)  # 新的描述
            new_data.extend(color_map)  # 颜色映射表
            new_data.extend(image_data)  # 图像数据
            new_data.extend(self._create_footer())  # 尾部
            
            # 写回文件
            with open(file_path, 'wb') as f:
                f.write(new_data)
                
        except Exception as e:
            print(f"修复图像时出错: {str(e)}")
            raise

def main():
    parser = argparse.ArgumentParser(description='小米手环7表盘转换工具')
    parser.add_argument('input', help='输入PNG文件路径')
    args = parser.parse_args()
    
    converter = WorkingTGAConverter()
    converter.pack(args.input)

if __name__ == '__main__':
    main()