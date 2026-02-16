using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

[CustomPropertyDrawer(typeof(Guid128))]
public class Guid128Drawer : PropertyDrawer
{
	public override void OnGUI(Rect position, SerializedProperty property, GUIContent label)
	{
		EditorGUI.BeginProperty(position, label, property);

		position = EditorGUI.PrefixLabel(position, GUIUtility.GetControlID(FocusType.Passive), label);

		var prop = property.FindPropertyRelative("data");
		var elem0 = prop.GetArrayElementAtIndex(0);
		var elem1 = prop.GetArrayElementAtIndex(1);
		var elem2 = prop.GetArrayElementAtIndex(2);
		var elem3 = prop.GetArrayElementAtIndex(3);

		var stringRep = $"{elem0.uintValue:X8}-{elem1.uintValue:X8}-{elem2.uintValue:X8}-{elem3.uintValue:X8}";

		EditorGUI.LabelField(position, stringRep);
		
		EditorGUI.EndProperty();
	}
}

[Serializable]
public class Guid128
{
	public const uint INVALID_VALUE_0 = 0xBADBADBA;
	public const uint INVALID_VALUE_1 = 0xBEEFBEEF;
	public const uint INVALID_VALUE_2 = 0xEAC15A55;
	public const uint INVALID_VALUE_3 = 0x91100911;

	[SerializeField] private int[] data = new int[4];

	public uint[] Data
	{
		get
		{
			var arr = new uint[data.Length];
			for (var i = 0; i < data.Length; i++)
			{
				arr[i] = unchecked((uint)data[i]);
			}
			return arr;
		}
		set
		{
			for (var i = 0; i < data.Length; i++)
			{
				data[i] = unchecked((int)value[i]);
			}
		}
	}

	public Guid128()
	{
		Invalidate();
	}

	public Guid128(uint val0, uint val1, uint val2, uint val3)
	{
		data[0] = unchecked((int)val0);
		data[1] = unchecked((int)val1);
		data[2] = unchecked((int)val2);
		data[3] = unchecked((int)val3);
	}

	public Guid128(BinaryReader reader)
		: this(
			reader.ReadUInt32BigEndian(),
			reader.ReadUInt32BigEndian(),
			reader.ReadUInt32BigEndian(),
			reader.ReadUInt32BigEndian())
	{ }

	public void Clear()
	{
		data[0] = 0;
		data[1] = 0;
		data[2] = 0;
		data[3] = 0;
	}

	public void Invalidate()
	{
		data[0] = unchecked((int)INVALID_VALUE_0);
		data[1] = unchecked((int)INVALID_VALUE_1);
		data[2] = unchecked((int)INVALID_VALUE_2);
		data[3] = unchecked((int)INVALID_VALUE_3);
	}

	public bool IsClear()
	{
		return Data[0] == 0
		       && Data[1] == 0
		       && Data[2] == 0
		       && Data[3] == 0;
	}

	public bool IsValid()
	{
		return Data[0] != INVALID_VALUE_0
		       || Data[1] != INVALID_VALUE_1
		       || Data[2] != INVALID_VALUE_2
		       || Data[3] != INVALID_VALUE_3;
	}

	public uint this[int index] => Data[index];

	public static bool operator ==(Guid128 a, Guid128 b)
	{
		if (a is null != b is null)
		{
			return false;
		}

		if (a is null && b is null)
		{
			return true;
		}

		return a.data.SequenceEqual(b.data);
	}

	public static bool operator !=(Guid128 a, Guid128 b)
	{
		return !(a == b);
	}

	public override string ToString()
	{
		return $"{Data[0]:X8}-{Data[1]:X8}-{Data[2]:X8}-{Data[3]:X8}";
	}
}