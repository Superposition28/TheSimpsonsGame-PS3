using BCnEncoder.Decoder;
using BCnEncoder.Shared;
using System;
using System.IO;
using TreeEditor;
using UnityEngine;

namespace RWReader.Sections
{
	[Serializable]
	public class TextureNative : Section
	{
		public TextureNative()
		{
			Name = "Texture Native";
			Header.ClumpID = 0x00000015;
			DataStorageType = SectionDataStorage.DataInStruct;
			CanHaveChildren = true;
		}

		public int DeviceID;
		public int FilterFlags;
		public string TextureName;
		public string AlphaName;
		public int RasterFlags;
		public uint CompressionType;
		public ushort Width;
		public ushort Height;
		public byte BitDepth;
		public byte MipmapCount;
		public byte Unknown_Const4;
		public byte Compression;

		[NonSerialized]
		public int DataSize;
		[NonSerialized]
		public byte[] DataBytes;

		[NonSerialized]
		public int ExtensionSize;
		[NonSerialized]
		public byte[] ExtensionBytes;

		public Texture2D Texture;

		public override void Deserialize(BinaryReader reader)
		{
			DeviceID = reader.ReadInt32BigEndian();
			FilterFlags = reader.ReadInt32BigEndian();
			TextureName = reader.ReadStringBytes(32);
			AlphaName = reader.ReadStringBytes(32);
			RasterFlags = reader.ReadInt32BigEndian();
			CompressionType = reader.ReadUInt32BigEndian();
			Width = reader.ReadUInt16BigEndian();
			Height = reader.ReadUInt16BigEndian();
			BitDepth = reader.ReadByte();
			MipmapCount = reader.ReadByte();
			Unknown_Const4 = reader.ReadByte();
			Compression = reader.ReadByte();

			DataSize = reader.ReadInt32(); // little endian
			DataBytes = reader.ReadBytes(DataSize);

			if (reader.BaseStream.Position != reader.BaseStream.Length)
			{
				ExtensionSize = reader.ReadInt32(); // little endian
				ExtensionBytes = reader.ReadBytes(ExtensionSize);
			}

			switch (CompressionType)
			{
				case 438305106: // BC1
				{
					var decoder = new BcDecoder();
					var image = decoder.DecodeRaw(DataBytes, Width, Height, CompressionFormat.Bc1);
					Texture = new Texture2D(Width, Height, TextureFormat.RGBA32, false);
					Texture.SetPixelData(image, 0);
					Texture.Apply(false);
					break;
				}

				case 438305107: // BC2
				{
					var decoder = new BcDecoder();
					var image = decoder.DecodeRaw(DataBytes, Width, Height, CompressionFormat.Bc2);
					Texture = new Texture2D(Width, Height, TextureFormat.RGBA32, false);
					Texture.SetPixelData(image, 0);
					Texture.Apply(false);
					break;
				}

				case 438305108: // BC3
				{
					var decoder = new BcDecoder();
					var image = decoder.DecodeRaw(DataBytes, Width, Height, CompressionFormat.Bc3);
					Texture = new Texture2D(Width, Height, TextureFormat.RGBA32, false);
					Texture.SetPixelData(image, 0);
					Texture.Apply(false);
					break;
				}

				case 405275014: // BGRA32
				{
					try
					{
						var unswizzled = UnswizzleMorton(DataBytes, Width, Height, 4);
						Texture = new Texture2D(Width, Height, TextureFormat.BGRA32, false);
						Texture.alphaIsTransparency = true;
						Texture.LoadRawTextureData(unswizzled);
						Texture.Apply(false);
						break;
					}
					catch (Exception e)
					{
						Debug.LogError($"Exception while deserializing {TextureName}: {e}");
						return;
					}
				}

				case 671088898: // A8
				{
					try
					{
						var unswizzled = UnswizzleMorton(DataBytes, Width, Height, 1);
						Texture = new Texture2D(Width, Height, TextureFormat.Alpha8, false);
						Texture.alphaIsTransparency = true;
						Texture.LoadRawTextureData(unswizzled);
						Texture.Apply(false);
					}
					catch (Exception e)
					{
						Debug.LogError($"Exception while deserializing {TextureName}: {e}");
						return;
					}
					
					break;
				}

				default:
					Debug.LogError($"{CompressionType} not implemented");
					return;
			}

			// flip texture vertically

			var pixels = Texture.GetPixels();
			for (var y = 0; y < Height / 2; y++)
			{
				var topRow = y * Width;
				var bottomRow = (Height - 1 - y) * Width;

				for (var x = 0; x < Width; x++)
				{
					var topIndex = topRow + x;
					var bottomIndex = bottomRow + x;

					(pixels[topIndex], pixels[bottomIndex]) = (pixels[bottomIndex], pixels[topIndex]);
				}
			}

			Texture.SetPixels(pixels);
			Texture.Apply(false, true);

			//Console.WriteLine($"TextureName:{TextureName}, SDBM:{new SDBMHash(TextureName).Value}");
		}

		static int MortonDecode(int x, int y)
		{
			int morton = 0;
			for (int i = 0; i < 16; i++)
			{
				morton |= ((x >> i) & 1) << (2 * i);
				morton |= ((y >> i) & 1) << (2 * i + 1);
			}
			return morton;
		}

		static byte[] UnswizzleMorton(
			byte[] src,
			int width,
			int height,
			int bytesPerPixel)
		{
			var dst = new byte[width * height * bytesPerPixel];

			for (int y = 0; y < height; y++)
			{
				for (int x = 0; x < width; x++)
				{
					int srcPixel = MortonDecode(x, y);
					int dstPixel = y * width + x;

					Buffer.BlockCopy(
						src,
						srcPixel * bytesPerPixel,
						dst,
						dstPixel * bytesPerPixel,
						bytesPerPixel
					);
				}
			}

			return dst;
		}
	}
}