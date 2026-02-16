using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using RWReader.RWStructs;
using Unity.VisualScripting.Antlr3.Runtime;
using UnityEngine;

public static class Extensions
{
	public static float Map(this float value, float from1, float to1, float from2, float to2)
	{
		return (value - from1) / (to1 - from1) * (to2 - from2) + from2;
	}

	public static float Map(this int value, float from1, float to1, float from2, float to2)
	{
		return (value - from1) / (to1 - from1) * (to2 - from2) + from2;
	}

	public static void Align(this BinaryReader reader, int n)
	{
		reader.BaseStream.Position = (reader.BaseStream.Position + (n - 1)) & ~(n - 1);
	}

	public static Vector3 ReadVector3BigEndian(this BinaryReader reader)
		=> new(reader.ReadSingleBigEndian(), reader.ReadSingleBigEndian(), reader.ReadSingleBigEndian());

	public static Vector4 ReadVector4BigEndian(this BinaryReader reader)
		=> new(reader.ReadSingleBigEndian(), reader.ReadSingleBigEndian(), reader.ReadSingleBigEndian(), reader.ReadSingleBigEndian());

	public static Quaternion ReadQuaternionBigEndian(this BinaryReader reader)
		=> new(reader.ReadSingleBigEndian(), reader.ReadSingleBigEndian(), reader.ReadSingleBigEndian(), reader.ReadSingleBigEndian());

	/// <summary>
	/// Reads a 32-bit boolean value.
	/// </summary>
	public static bool ReadBool32(this BinaryReader reader)
		=> reader.ReadInt32() == 1;

	public static Color ReadRwRGBA(this BinaryReader reader)
	{
		var r = reader.ReadByte() / 255f;
		var g = reader.ReadByte() / 255f;
		var b = reader.ReadByte() / 255f;
		var a = reader.ReadByte() / 255f;
		return new Color(r, g, b, a);
	}

	public static string ReadStringBytes(this BinaryReader reader, int byteCount)
	{
		var bytes = reader.ReadBytes(byteCount);

		var builder = new StringBuilder();

		foreach (var b in bytes)
		{
			if (b == 0x00)
			{
				break;
			}

			builder.Append(Encoding.ASCII.GetString(new[] { b })); // this seems dumb, better way?
		}

		return builder.ToString();
	}

	public static string ReadNullTerminatedString(this BinaryReader reader)
	{
		var bytes = new List<byte>();

		if (reader.BaseStream.Position >= reader.BaseStream.Length)
		{
			return "EXCEEDED STREAM LENGTH!";
		}

		var readByte = reader.ReadByte();
		while (readByte != 0x00)
		{
			bytes.Add(readByte);
			readByte = reader.ReadByte();
		}

		return Encoding.UTF8.GetString(bytes.ToArray());
	}

	public static string ReadNullTerminatedStringAtPointer(this BinaryReader reader, int offset = 0)
	{
		offset += reader.ReadInt32BigEndian();
		var savedPos = reader.BaseStream.Position;
		reader.BaseStream.Position = offset;

		var sb = new StringBuilder();
		byte read;
		while ((read = reader.ReadByte()) != 0x00)
		{
			sb.Append((char)read);
		}

		reader.BaseStream.Position = savedPos;

		return sb.ToString();
	}

	public static string ReadRWString(this BinaryReader reader)
	{
		var length = reader.ReadInt32BigEndian();
		var bytes = reader.ReadBytes(length);

		var sb = new StringBuilder();
		foreach (var b in bytes)
		{
			if (b == 0x00)
			{
				break;
			}

			sb.Append((char)b);
		}

		return sb.ToString();
	}

	public static short ReadInt16BigEndian(this BinaryReader reader) => BinaryPrimitives.ReadInt16BigEndian(reader.ReadBytes(2));
	public static ushort ReadUInt16BigEndian(this BinaryReader reader) => BinaryPrimitives.ReadUInt16BigEndian(reader.ReadBytes(2));

	public static int ReadInt32BigEndian(this BinaryReader reader) => BinaryPrimitives.ReadInt32BigEndian(reader.ReadBytes(4));
	public static uint ReadUInt32BigEndian(this BinaryReader reader) => BinaryPrimitives.ReadUInt32BigEndian(reader.ReadBytes(4));

	public static long ReadInt64BigEndian(this BinaryReader reader) => BinaryPrimitives.ReadInt64BigEndian(reader.ReadBytes(8));
	public static ulong ReadUInt64BigEndian(this BinaryReader reader) => BinaryPrimitives.ReadUInt64BigEndian(reader.ReadBytes(8));

	public static float ReadSingleBigEndian(this BinaryReader reader) => ReadSingleBigEndian(reader.ReadBytes(4));

	public static float ReadSingleBigEndian(ReadOnlySpan<byte> source)
	{
		return BitConverter.IsLittleEndian ?
			BitConverter.Int32BitsToSingle(BinaryPrimitives.ReverseEndianness(MemoryMarshal.Read<int>(source))) :
			MemoryMarshal.Read<float>(source);
	}

	public static Vector3 ReadRwV3d(this BinaryReader reader)
	{
		return new Vector3(reader.ReadSingleBigEndian(), reader.ReadSingleBigEndian(), reader.ReadSingleBigEndian());
	}

	public static bool GetBit(this byte b, int n)
	{
		return (b & (1 << n)) != 0;
	}

	public static bool GetBit(this uint b, int n)
	{
		return (b & (1 << n)) != 0;
	}

	public static int ToInt32BigEndian(this byte[] arr)
	{
		if (BitConverter.IsLittleEndian)
		{
			Array.Reverse(arr);
		}

		return BitConverter.ToInt32(arr);
	}

	public static uint ToUInt32BigEndian(this byte[] arr)
	{
		if (BitConverter.IsLittleEndian)
		{
			Array.Reverse(arr);
		}

		return BitConverter.ToUInt32(arr);
	}

	public static float ToSingleBigEndian(this byte[] arr)
	{
		if (BitConverter.IsLittleEndian)
		{
			Array.Reverse(arr);
		}

		return BitConverter.ToSingle(arr);
	}

	public static Sphere ReadRwSphere(this BinaryReader reader)
		=> new(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle());
}