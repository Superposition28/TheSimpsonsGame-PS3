using System;
using System.IO;

public static class Refpack
{
	public static byte[] Decompress(byte[] data)
	{
		var memoryStream = new MemoryStream(data);
		return Decompress(memoryStream);
	}

	public static byte[] Decompress(Stream input)
	{
		var dummy = new byte[4];
		if (input.Read(dummy, 0, 2) != 2)
		{
			throw new EndOfStreamException("could not read header");
		}

		var header = dummy[0] << 8 | dummy[1];
		if ((header & 0x1FFF) != 0x10FB)
		{
			throw new InvalidOperationException("input is not compressed");
		}

		var isLong = (header & 0x8000) != 0;
		var isDoubled = (header & 0x0100) != 0;

		if (isDoubled == true)
		{
			throw new InvalidOperationException("this should never happen");
		}

		uint uncompressedSize;
		if (isLong == true)
		{
			if (input.Read(dummy, 0, 4) != 4)
			{
				throw new EndOfStreamException("could not read uncompressed size");
			}
			uncompressedSize = (uint)(dummy[0] << 24) |
			                   (uint)(dummy[1] << 16) |
			                   (uint)(dummy[2] << 8) |
			                   (uint)(dummy[3] << 0);
		}
		else
		{
			if (input.Read(dummy, 0, 3) != 3)
			{
				throw new EndOfStreamException("could not read uncompressed size");
			}
			uncompressedSize = (uint)(dummy[0] << 16) |
			                   (uint)(dummy[1] << 8) |
			                   (uint)(dummy[2] << 0);
		}

		var data = new byte[uncompressedSize];
		uint offset = 0;
		while (true)
		{
			var stop = false;
			uint plainSize;
			var copySize = 0u;
			var copyOffset = 0u;

			if (input.Read(dummy, 0, 1) != 1)
			{
				throw new EndOfStreamException("could not read prefix");
			}
			var prefix = dummy[0];

			if (prefix < 0x80)
			{
				if (input.Read(dummy, 0, 1) != 1)
				{
					throw new EndOfStreamException("could not read extra");
				}

				plainSize = (uint)(prefix & 0x03);
				copySize = (uint)(((prefix & 0x1C) >> 2) + 3);
				copyOffset = (uint)(((prefix & 0x60) << 3 | dummy[0]) + 1);
			}
			else if (prefix < 0xC0)
			{
				if (input.Read(dummy, 0, 2) != 2)
				{
					throw new EndOfStreamException("could not read extra");
				}

				plainSize = (uint)(dummy[0] >> 6);
				copySize = (uint)((prefix & 0x3F) + 4);
				copyOffset = (uint)(((dummy[0] & 0x3F) << 8 | dummy[1]) + 1);
			}
			else if (prefix < 0xE0)
			{
				if (input.Read(dummy, 0, 3) != 3)
				{
					throw new EndOfStreamException("could not read extra");
				}

				plainSize = (uint)(prefix & 3);
				copySize = (uint)(((prefix & 0x0C) << 6 | dummy[2]) + 5);
				copyOffset = (uint)((((prefix & 0x10) << 4 | dummy[0]) << 8 | dummy[1]) + 1);
			}
			else if (prefix < 0xFC)
			{
				plainSize = (uint)(((prefix & 0x1F) + 1) * 4);
			}
			else
			{
				plainSize = (uint)(prefix & 3);
				stop = true;
			}

			if (plainSize > 0)
			{
				if (input.Read(data, (int)offset, (int)plainSize) != (int)plainSize)
				{
					throw new EndOfStreamException("could not read plain");
				}

				offset += plainSize;
			}

			if (copySize > 0)
			{
				for (uint i = 0; i < copySize; i++)
				{
					data[offset + i] = data[offset - copyOffset + i];
				}

				offset += copySize;
			}

			if (stop)
			{
				break;
			}
		}

		return data;
	}
}